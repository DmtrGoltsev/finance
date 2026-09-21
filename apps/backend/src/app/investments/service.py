from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from app.authz import Actor
from app.db.models import OutboxEvent

from .allocation import AllocationPolicy, RiskBucket, cash_first_rebalance
from .instrument_resolver import MoexInstrumentResolver
from .models import (
    InvestmentPolicyModel,
    PortfolioImportModel,
    PortfolioSnapshotModel,
    RecommendationJobModel,
    RecommendationReportModel,
)
from .repository import InvestmentRepository, canonical_hash
from .schemas import (
    InvestmentPolicyPutRequest,
    PortfolioImportConfirmRequest,
    PortfolioImportCreateRequest,
    RecommendationCallbackRequest,
    RecommendationJobCreateRequest,
)
from .source_validation import (
    UntrustedRecommendationSource,
    validate_recommendation_sources,
)

SNAPSHOT_FRESHNESS = timedelta(hours=24)
RECOMMENDATION_VALIDITY = timedelta(days=7)
CALLBACK_NONCE_TTL = timedelta(minutes=10)
DISCLAIMER = (
    "Персональная аналитическая подсказка для владельца Finance. "
    "Не является индивидуальной инвестиционной рекомендацией и не исполняет сделки."
)


class InvestmentServiceError(Exception):
    code = "INVESTMENT_SERVICE_ERROR"


class ResourceNotFoundOrInaccessible(InvestmentServiceError):
    code = "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"


class IdempotencyConflict(InvestmentServiceError):
    code = "IDEMPOTENCY_KEY_REUSED"


class InvalidTransition(InvestmentServiceError):
    code = "INVALID_RECOMMENDATION_TRANSITION"


class DeliveryRetryRequired(InvestmentServiceError):
    code = "DELIVERY_RETRY_REQUIRED"


class StalePortfolio(InvestmentServiceError):
    code = "PORTFOLIO_DATA_STALE"


class StaleMarketData(InvestmentServiceError):
    code = "MARKET_DATA_STALE"


class ReplayDetected(InvestmentServiceError):
    code = "CALLBACK_REPLAY_DETECTED"


class InvalidObservedAt(InvestmentServiceError):
    code = "PORTFOLIO_OBSERVED_AT_INVALID"


class InvalidRecommendationPayload(InvestmentServiceError):
    code = "INVALID_RECOMMENDATION_PAYLOAD"


class ConcurrentTransition(InvestmentServiceError):
    code = "CONCURRENT_RECOMMENDATION_TRANSITION"


class AccountProfileConflict(InvestmentServiceError):
    code = "ACCOUNT_PROFILE_CONFLICT"


class ConfirmedImportNotDiscardable(InvestmentServiceError):
    code = "CONFIRMED_IMPORT_NOT_DISCARDABLE"


class InvalidPagination(InvestmentServiceError):
    code = "INVALID_PAGINATION_CURSOR"


class InvestmentService:
    def __init__(
        self,
        repository: InvestmentRepository,
        *,
        now: datetime | None = None,
        issuer_source_hosts: list[str] | None = None,
        instrument_resolver: MoexInstrumentResolver | None = None,
    ) -> None:
        self.repo = repository
        self._fixed_now = now
        self._issuer_source_hosts = issuer_source_hosts or []
        self._instrument_resolver = instrument_resolver or MoexInstrumentResolver(
            repository.session, now=now
        )

    @property
    def now(self) -> datetime:
        return self._fixed_now or datetime.now(UTC)

    def policy(self, actor: Actor) -> InvestmentPolicyModel:
        owner = _actor_uuid(actor)
        model = self.repo.get_policy(owner)
        if model is not None:
            return model
        return self.repo.save_policy(
            owner_user_id=owner,
            conservative=Decimal("40"),
            moderate=Decimal("30"),
            aggressive=Decimal("30"),
            tolerance=Decimal("5"),
        )

    def put_policy(
        self, actor: Actor, request: InvestmentPolicyPutRequest
    ) -> InvestmentPolicyModel:
        owner = _actor_uuid(actor)
        return self.repo.save_policy(
            owner_user_id=owner,
            conservative=request.conservative_percent,
            moderate=request.moderate_percent,
            aggressive=request.aggressive_percent,
            tolerance=request.tolerance_percent,
        )

    def create_import(
        self, actor: Actor, request: PortfolioImportCreateRequest
    ) -> PortfolioImportModel:
        owner = _actor_uuid(actor)
        if _utc(request.observed_at) > self.now + timedelta(minutes=5):
            raise InvalidObservedAt()
        payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        request_hash = canonical_hash(payload)
        existing = self.repo.find_import_by_idempotency(owner, request.idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflict()
            return existing
        profile = self.repo.get_account_profile(request.account_profile_id)
        label_key = _account_label_key(request.user_label)
        if profile is not None and profile.owner_user_id != owner:
            raise ResourceNotFoundOrInaccessible()
        if profile is None:
            profile = self.repo.create_account_profile(
                profile_id=request.account_profile_id,
                owner_user_id=owner,
                brokerage=str(request.brokerage),
                user_label=request.user_label,
                label_key=label_key,
                account_type=str(request.account_type),
            )
        if (
            profile.id != request.account_profile_id
            or profile.owner_user_id != owner
            or profile.brokerage != str(request.brokerage)
            or profile.label_key != label_key
            or profile.account_type != str(request.account_type)
        ):
            raise AccountProfileConflict()
        created = self.repo.create_import(
            owner_user_id=owner,
            brokerage=str(request.brokerage),
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            screenshot_count=request.screenshot_count,
            observed_at=request.observed_at,
            account_profile_id=profile.id,
        )
        if created.request_hash != request_hash:
            raise IdempotencyConflict()
        return created

    def confirm_import(
        self,
        actor: Actor,
        import_id: UUID,
        request: PortfolioImportConfirmRequest,
    ) -> PortfolioSnapshotModel:
        owner = _actor_uuid(actor)
        imported = self.repo.get_import(import_id)
        if imported is None or imported.owner_user_id != owner:
            raise ResourceNotFoundOrInaccessible()
        if imported.account_profile_id != request.account_profile_id:
            raise AccountProfileConflict()
        existing = self.repo.get_snapshot_by_import(import_id)
        if existing is not None:
            return existing
        return self.repo.confirm_import(
            import_model=imported,
            free_cash=request.free_cash,
            monthly_contribution=request.monthly_contribution,
            positions=request.positions,
        )

    def discard_import(self, actor: Actor, import_id: UUID) -> None:
        owner = _actor_uuid(actor)
        imported = self.repo.get_import(import_id)
        if imported is None or imported.owner_user_id != owner:
            return
        if imported.status != "pending":
            raise ConfirmedImportNotDiscardable()
        self.repo.discard_pending_import(import_id, owner)

    def snapshot(self, actor: Actor, snapshot_id: UUID) -> PortfolioSnapshotModel:
        owner = _actor_uuid(actor)
        model = self.repo.get_snapshot(snapshot_id)
        if model is None or model.owner_user_id != owner:
            raise ResourceNotFoundOrInaccessible()
        return model

    def snapshots(self, actor: Actor) -> list[PortfolioSnapshotModel]:
        return self.repo.list_snapshots(_actor_uuid(actor))

    def create_job(
        self, actor: Actor, request: RecommendationJobCreateRequest
    ) -> RecommendationJobModel:
        owner = _actor_uuid(actor)
        request_hash = canonical_hash(
            {"snapshotIds": sorted(str(item) for item in request.snapshot_ids)}
        )
        existing = self.repo.find_job_by_idempotency(owner, request.idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflict()
            return existing

        if self.repo.session.scalar(
            select(RecommendationJobModel.id)
            .where(
                RecommendationJobModel.owner_user_id == owner,
                RecommendationJobModel.status == "failed",
                RecommendationJobModel.last_error_code == "delivery_failed",
            )
            .limit(1)
        ):
            raise DeliveryRetryRequired()

        snapshots: list[PortfolioSnapshotModel] = []
        for snapshot_id in request.snapshot_ids:
            snapshot = self.repo.get_snapshot(snapshot_id)
            if snapshot is None or snapshot.owner_user_id != owner:
                raise ResourceNotFoundOrInaccessible()
            if _utc(snapshot.observed_at) < self.now - SNAPSHOT_FRESHNESS:
                raise StalePortfolio()
            snapshots.append(snapshot)

        policy = self.policy(actor)
        analysis_package = self._analysis_package(snapshots, policy)
        created = self.repo.create_job(
            owner_user_id=owner,
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            snapshots=snapshots,
            analysis_package=analysis_package,
        )
        if created.request_hash != request_hash:
            raise IdempotencyConflict()
        return created

    def job(self, actor: Actor, job_id: UUID) -> RecommendationJobModel:
        owner = _actor_uuid(actor)
        model = self.repo.get_job(job_id)
        if model is None or model.owner_user_id != owner:
            raise ResourceNotFoundOrInaccessible()
        return model

    def retry_delivery(self, actor: Actor, job_id: UUID) -> RecommendationJobModel:
        owner = _actor_uuid(actor)
        # Match dispatcher lock order: event first, job second. Never allocate a new event.
        event = self.repo.session.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.aggregate_id == job_id,
                OutboxEvent.owner_user_id == owner,
                OutboxEvent.event_type == "investment.recommendation.requested.v1",
            )
            .order_by(OutboxEvent.attempt_count.desc())
            .limit(1)
            .with_for_update()
        )
        if event is None:
            raise ResourceNotFoundOrInaccessible()
        job = self.repo.get_job_for_update(job_id)
        if job is None or job.owner_user_id != owner:
            raise ResourceNotFoundOrInaccessible()
        if job.status != "failed" or job.last_error_code != "delivery_failed":
            # Repeated clicks cannot reset an active lease/backoff or create another job.
            if job.status in {"queued", "collecting", "analyzing", "ready"}:
                return job
            raise InvalidTransition()
        if event.status != "dead" or event.attempt_count + 1 != job.attempt_count:
            raise InvalidTransition()
        changed = self.repo.session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event.id,
                OutboxEvent.status == "dead",
            )
            .values(
                status="pending",
                delivery_attempts=0,
                available_at=self.now,
                processed_at=None,
                lease_token=None,
                lease_until=None,
            )
        )
        if changed.rowcount != 1:
            self.repo.session.refresh(job)
            return job
        updated = self.repo.conditional_update_job(
            job_id=job.id,
            expected_version=job.version,
            values={
                "status": "queued",
                # Keep the marker until the saved terminal callback arrives. It is the
                # only condition under which queued -> ready is allowed directly.
                "last_error_code": "delivery_failed",
                "completed_at": None,
                "updated_at": self.now,
            },
        )
        if updated is None:
            self.repo.session.rollback()
            raise InvalidTransition()
        return updated

    def jobs(
        self, actor: Actor, *, limit: int, cursor: str | None
    ) -> tuple[list[RecommendationJobModel], str | None, bool]:
        try:
            offset = 0 if cursor is None else int(cursor)
        except ValueError as exc:
            raise InvalidPagination() from exc
        if offset < 0:
            raise InvalidPagination()
        items, has_more = self.repo.list_jobs(
            _actor_uuid(actor), offset=offset, limit=limit
        )
        next_cursor = str(offset + len(items)) if has_more else None
        return items, next_cursor, has_more

    def report(self, actor: Actor, job_id: UUID) -> RecommendationReportModel:
        self.job(actor, job_id)
        report = self.repo.report_for_job(job_id)
        if report is None:
            raise ResourceNotFoundOrInaccessible()
        report.generated_at = _utc(report.generated_at)
        report.valid_until = _utc(report.valid_until)
        return report

    def apply_callback(
        self,
        *,
        job_id: UUID,
        nonce: str,
        request: RecommendationCallbackRequest,
    ) -> RecommendationJobModel:
        job = self.repo.get_job_for_update(job_id)
        if job is None:
            raise ResourceNotFoundOrInaccessible()
        if not self.repo.record_nonce(
            job_id=job.id,
            nonce=nonce,
            received_at=self.now,
            expires_at=self.now + CALLBACK_NONCE_TTL,
        ):
            raise ReplayDetected()

        status = str(request.status)
        allowed = {
            "queued": {"collecting", "analyzing", "failed"},
            "collecting": {"analyzing", "ready", "failed"},
            "analyzing": {"ready", "failed"},
            "ready": set(),
            "failed": set(),
        }
        recovered_ready = (
            job.status == "queued"
            and job.last_error_code == "delivery_failed"
            and status == "ready"
        )
        repeated_ready = job.status == "ready" and status == "ready"
        if status not in allowed[job.status] and not recovered_ready and not repeated_ready:
            raise InvalidTransition()

        ready_hash = (
            canonical_hash(request.model_dump(mode="json", by_alias=True))
            if status == "ready"
            else None
        )
        if repeated_ready:
            report = self.repo.report_for_job(job.id)
            if report is None or report.callback_hash != ready_hash:
                raise InvalidTransition()
            self._complete_requested_delivery(job)
            return job

        if request.market_data_as_of is not None:
            market_time = _utc(request.market_data_as_of)
            if market_time < self.now - SNAPSHOT_FRESHNESS or market_time > self.now + timedelta(
                minutes=5
            ):
                raise StaleMarketData()
        else:
            market_time = job.market_data_as_of

        validated_sources = []
        if status == "ready":
            try:
                validated_sources = validate_recommendation_sources(
                    request.sources,
                    issuer_hosts=self._issuer_source_hosts,
                    allow_tax_sources=self._job_has_tax_advantaged_position(job),
                )
            except UntrustedRecommendationSource as exc:
                raise InvalidRecommendationPayload() from exc
            self._validate_ready_payload(job, request)

        if status == "failed" and request.retryable and job.attempt_count < 3:
            updated = self.repo.conditional_update_job(
                job_id=job.id,
                expected_version=job.version,
                values={
                    "attempt_count": job.attempt_count + 1,
                    "status": "queued",
                    "last_error_code": request.error_code,
                    "updated_at": self.now,
                    "market_data_as_of": market_time,
                },
            )
            if updated is None:
                raise ConcurrentTransition()
            self.repo.enqueue_job(
                updated,
                {"schemaVersion": 1, "jobId": str(updated.id), "retry": True},
            )
            self.repo.session.flush()
            return updated

        completed_at = self.now if status in {"ready", "failed"} else None
        updated = self.repo.conditional_update_job(
            job_id=job.id,
            expected_version=job.version,
            values={
                "status": status,
                "last_error_code": request.error_code,
                "updated_at": self.now,
                "market_data_as_of": market_time,
                "completed_at": completed_at,
            },
        )
        if updated is None:
            raise ConcurrentTransition()
        if status == "ready":
            generated_at = self.now
            report = self.repo.save_report(
                job=updated,
                summary=request.summary or "",
                assumptions=request.assumptions,
                generated_at=generated_at,
                valid_until=generated_at + RECOMMENDATION_VALIDITY,
                disclaimer=DISCLAIMER,
                callback_hash=ready_hash,
                actions=request.actions,
                sources=validated_sources,
            )
            self.repo.enqueue_ready_notification(updated, report)
            self._complete_requested_delivery(updated)
        self.repo.session.flush()
        return updated

    def _complete_requested_delivery(self, job: RecommendationJobModel) -> None:
        self.repo.session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.aggregate_id == job.id,
                OutboxEvent.owner_user_id == job.owner_user_id,
                OutboxEvent.event_type == "investment.recommendation.requested.v1",
                OutboxEvent.attempt_count == job.attempt_count - 1,
                OutboxEvent.status != "processed",
            )
            .values(
                status="processed",
                lease_token=None,
                lease_until=None,
                processed_at=self.now,
            )
        )

    def cash_first_adjustments(self, job: RecommendationJobModel) -> list[Any]:
        snapshots = [self.repo.get_snapshot(item) for item in self.repo.job_snapshot_ids(job.id)]
        snapshots = [item for item in snapshots if item is not None]
        policy = self._allocation_policy(job)
        current = {bucket: Decimal("0") for bucket in RiskBucket}
        for snapshot in snapshots:
            for position in self.repo.positions(snapshot.id):
                current[RiskBucket(position.risk_bucket)] += position.market_value
        return cash_first_rebalance(
            current_values=current,
            free_cash=sum((item.free_cash for item in snapshots), Decimal("0")),
            monthly_contribution=sum(
                (item.monthly_contribution for item in snapshots), Decimal("0")
            ),
            policy=policy,
        )

    def _analysis_package(
        self,
        snapshots: list[PortfolioSnapshotModel],
        policy: InvestmentPolicyModel,
    ) -> dict[str, Any]:
        positions: list[dict[str, Any]] = []
        for snapshot in snapshots:
            for item in self.repo.positions(snapshot.id):
                resolved = self._instrument_resolver.resolve(secid=item.ticker, isin=item.isin)
                if resolved is None:
                    raise InvalidRecommendationPayload()
                positions.append(
                    {
                        "secid": resolved.secid,
                        "isin": resolved.isin,
                        "instrumentType": item.instrument_type,
                        "riskBucket": item.risk_bucket,
                        "quantity": str(item.quantity),
                        "marketValue": str(item.market_value),
                        "averagePrice": str(item.average_price)
                        if item.average_price is not None
                        else None,
                        "nominal": str(item.nominal) if item.nominal is not None else None,
                        "accruedInterest": str(item.accrued_interest)
                        if item.accrued_interest is not None
                        else None,
                        "couponRate": str(item.coupon_rate)
                        if item.coupon_rate is not None
                        else None,
                        "maturityDate": item.maturity_date.isoformat()
                        if item.maturity_date
                        else None,
                        "taxAccountType": item.tax_account_type,
                        "holdingStartedAt": item.holding_started_at.isoformat()
                        if item.holding_started_at
                        else None,
                        "estimatedFeeRate": str(item.estimated_fee_rate)
                        if item.estimated_fee_rate is not None
                        else None,
                    }
                )
        allowed_sources = [
            "moex.com",
            "cbr.ru",
            "minfin.gov.ru",
            "e-disclosure.ru",
            "interfax.ru",
            "tass.ru",
            "rbc.ru",
            "issuer-official-sites",
        ]
        if any(item["taxAccountType"] != "brokerage" for item in positions):
            allowed_sources.extend(["nalog.gov.ru", "www.nalog.gov.ru"])

        return {
            "schemaVersion": 1,
            "currency": "RUB",
            "market": "RU",
            "policy": {
                "conservativePercent": str(policy.conservative_percent),
                "moderatePercent": str(policy.moderate_percent),
                "aggressivePercent": str(policy.aggressive_percent),
                "tolerancePercent": str(policy.tolerance_percent),
            },
            "freeCash": str(sum((item.free_cash for item in snapshots), Decimal("0"))),
            "monthlyContribution": str(
                sum((item.monthly_contribution for item in snapshots), Decimal("0"))
            ),
            "positions": positions,
            "constraints": {
                "cashFirst": True,
                "automaticExecution": False,
                "marketDataMaxAgeHours": 24,
                "recommendationValidityDays": 7,
                "allowedSources": allowed_sources,
            },
        }

    def _job_has_tax_advantaged_position(self, job: RecommendationJobModel) -> bool:
        for snapshot_id in self.repo.job_snapshot_ids(job.id):
            if any(
                position.tax_account_type != "brokerage"
                for position in self.repo.positions(snapshot_id)
            ):
                return True
        return False

    def _validate_ready_payload(
        self,
        job: RecommendationJobModel,
        request: RecommendationCallbackRequest,
    ) -> None:
        policy = self._allocation_policy(job)
        adjustments = {str(item.bucket): item for item in self.cash_first_adjustments(job)}
        aggregates = {str(item.risk_bucket): item for item in request.aggregates}
        for bucket, adjustment in adjustments.items():
            aggregate = aggregates.get(bucket)
            if aggregate is None:
                raise InvalidRecommendationPayload()
            if aggregate.current_percent != adjustment.current_percent:
                raise InvalidRecommendationPayload()
            if aggregate.proposed_percent != adjustment.projected_percent:
                raise InvalidRecommendationPayload()
            if abs(aggregate.proposed_percent - adjustment.target_percent) > policy.tolerance:
                raise InvalidRecommendationPayload()

        known: dict[tuple[str, str], Any] = {}
        for snapshot_id in self.repo.job_snapshot_ids(job.id):
            for position in self.repo.positions(snapshot_id):
                if position.ticker:
                    known[("secid", position.ticker.casefold())] = position
                if position.isin:
                    known[("isin", position.isin.casefold())] = position

        additions = {bucket: Decimal("0") for bucket in adjustments}
        reductions = {bucket: Decimal("0") for bucket in adjustments}
        for action in request.actions:
            bucket = str(action.risk_bucket)
            adjustment = adjustments.get(bucket)
            if adjustment is None:
                raise InvalidRecommendationPayload()
            aggregate = aggregates[bucket]
            if (
                action.current_percent != aggregate.current_percent
                or action.target_percent != aggregate.proposed_percent
            ):
                raise InvalidRecommendationPayload()
            resolved = self._instrument_resolver.resolve(secid=action.ticker, isin=action.isin)
            if resolved is None:
                raise InvalidRecommendationPayload()
            position = None
            position = known.get(("secid", resolved.secid.casefold()))
            if position is None:
                position = known.get(("isin", resolved.isin.casefold()))
            action_name = str(action.action)
            if action_name in {"keep", "reduce", "increase"}:
                if position is None or position.risk_bucket != bucket:
                    raise InvalidRecommendationPayload()
            if action_name == "keep" and action.amount != 0:
                raise InvalidRecommendationPayload()
            if action_name == "reduce":
                if position is None or action.amount > position.market_value:
                    raise InvalidRecommendationPayload()
                reductions[bucket] += action.amount
            elif action_name in {"add", "increase"}:
                additions[bucket] += action.amount

        for bucket, adjustment in adjustments.items():
            if reductions[bucket] != adjustment.reduce_amount:
                raise InvalidRecommendationPayload()
            if additions[bucket] != adjustment.add_amount:
                raise InvalidRecommendationPayload()

    def _allocation_policy(self, job: RecommendationJobModel) -> AllocationPolicy:
        policy_model = self.repo.get_policy(job.owner_user_id)
        if policy_model is None:
            return AllocationPolicy()
        return AllocationPolicy(
            conservative=policy_model.conservative_percent,
            moderate=policy_model.moderate_percent,
            aggressive=policy_model.aggressive_percent,
            tolerance=policy_model.tolerance_percent,
        )


def _actor_uuid(actor: Actor) -> UUID:
    if not actor.user_id:
        raise ResourceNotFoundOrInaccessible()
    try:
        return UUID(actor.user_id)
    except ValueError as exc:
        raise ResourceNotFoundOrInaccessible() from exc


def _account_label_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
