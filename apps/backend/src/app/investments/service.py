from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.authz import Actor

from .allocation import AllocationPolicy, RiskBucket, cash_first_rebalance
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


class InvestmentService:
    def __init__(
        self,
        repository: InvestmentRepository,
        *,
        now: datetime | None = None,
        issuer_source_hosts: list[str] | None = None,
    ) -> None:
        self.repo = repository
        self._fixed_now = now
        self._issuer_source_hosts = issuer_source_hosts or []

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
        created = self.repo.create_import(
            owner_user_id=owner,
            brokerage=str(request.brokerage),
            idempotency_key=request.idempotency_key,
            request_hash=request_hash,
            screenshot_count=request.screenshot_count,
            observed_at=request.observed_at,
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
        existing = self.repo.get_snapshot_by_import(import_id)
        if existing is not None:
            return existing
        return self.repo.confirm_import(
            import_model=imported,
            free_cash=request.free_cash,
            monthly_contribution=request.monthly_contribution,
            positions=request.positions,
        )

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
        if status not in allowed[job.status]:
            raise InvalidTransition()

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
                actions=request.actions,
                sources=validated_sources,
            )
            self.repo.enqueue_ready_notification(updated, report)
        self.repo.session.flush()
        return updated

    def cash_first_adjustments(self, job: RecommendationJobModel) -> list[Any]:
        snapshots = [self.repo.get_snapshot(item) for item in self.repo.job_snapshot_ids(job.id)]
        snapshots = [item for item in snapshots if item is not None]
        policy_model = self.repo.get_policy(job.owner_user_id)
        if policy_model is None:
            policy = AllocationPolicy()
        else:
            policy = AllocationPolicy(
                conservative=policy_model.conservative_percent,
                moderate=policy_model.moderate_percent,
                aggressive=policy_model.aggressive_percent,
                tolerance=policy_model.tolerance_percent,
            )
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
                positions.append(
                    {
                        "secid": item.ticker,
                        "isin": item.isin,
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
                "allowedSources": [
                    "moex.com",
                    "cbr.ru",
                    "minfin.gov.ru",
                    "e-disclosure.ru",
                    "interfax.ru",
                    "tass.ru",
                    "rbc.ru",
                    "issuer-official-sites",
                ],
            },
        }

    def _validate_ready_payload(
        self,
        job: RecommendationJobModel,
        request: RecommendationCallbackRequest,
    ) -> None:
        adjustments = {str(item.bucket): item for item in self.cash_first_adjustments(job)}
        aggregates = {str(item.risk_bucket): item for item in request.aggregates}
        epsilon = Decimal("0.0100")
        for bucket, adjustment in adjustments.items():
            aggregate = aggregates.get(bucket)
            if aggregate is None:
                raise InvalidRecommendationPayload()
            if abs(aggregate.current_percent - adjustment.current_percent) > epsilon:
                raise InvalidRecommendationPayload()
            if abs(aggregate.proposed_percent - adjustment.projected_percent) > epsilon:
                raise InvalidRecommendationPayload()
            if abs(aggregate.proposed_percent - adjustment.target_percent) > Decimal("5"):
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
            position = None
            if action.ticker:
                position = known.get(("secid", action.ticker.casefold()))
            if position is None and action.isin:
                position = known.get(("isin", action.isin.casefold()))
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
            if reductions[bucket] > adjustment.reduce_amount + Decimal("0.0001"):
                raise InvalidRecommendationPayload()
            if additions[bucket] > adjustment.add_amount + Decimal("0.0001"):
                raise InvalidRecommendationPayload()


def _actor_uuid(actor: Actor) -> UUID:
    if not actor.user_id:
        raise ResourceNotFoundOrInaccessible()
    try:
        return UUID(actor.user_id)
    except ValueError as exc:
        raise ResourceNotFoundOrInaccessible() from exc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
