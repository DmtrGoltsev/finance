from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import OutboxEvent

from .models import (
    InvestmentPolicyModel,
    PortfolioImportModel,
    PortfolioPositionModel,
    PortfolioSnapshotModel,
    RecommendationActionModel,
    RecommendationCallbackNonceModel,
    RecommendationJobModel,
    RecommendationJobSnapshotModel,
    RecommendationReportModel,
    RecommendationSourceModel,
)
from .schemas import PortfolioPositionInput, RecommendationActionInput
from .source_validation import ValidatedRecommendationSource


class InvestmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_policy(self, owner_user_id: UUID) -> InvestmentPolicyModel | None:
        return self.session.scalar(
            select(InvestmentPolicyModel).where(
                InvestmentPolicyModel.owner_user_id == owner_user_id
            )
        )

    def save_policy(
        self,
        *,
        owner_user_id: UUID,
        conservative: Decimal,
        moderate: Decimal,
        aggressive: Decimal,
        tolerance: Decimal,
    ) -> InvestmentPolicyModel:
        now = datetime.now(UTC)
        model = self.get_policy(owner_user_id)
        if model is None:
            model = InvestmentPolicyModel(
                owner_user_id=owner_user_id,
                conservative_percent=conservative,
                moderate_percent=moderate,
                aggressive_percent=aggressive,
                tolerance_percent=tolerance,
                created_at=now,
                updated_at=now,
                version=1,
            )
            self.session.add(model)
        else:
            model.conservative_percent = conservative
            model.moderate_percent = moderate
            model.aggressive_percent = aggressive
            model.tolerance_percent = tolerance
            model.updated_at = now
            model.version += 1
        self.session.flush()
        return model

    def find_import_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> PortfolioImportModel | None:
        return self.session.scalar(
            select(PortfolioImportModel).where(
                PortfolioImportModel.owner_user_id == owner_user_id,
                PortfolioImportModel.idempotency_key == idempotency_key,
            )
        )

    def create_import(
        self,
        *,
        owner_user_id: UUID,
        brokerage: str,
        idempotency_key: str,
        request_hash: str,
        screenshot_count: int,
        observed_at: datetime,
    ) -> PortfolioImportModel:
        now = datetime.now(UTC)
        model = PortfolioImportModel(
            owner_user_id=owner_user_id,
            brokerage=brokerage,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            screenshot_count=screenshot_count,
            observed_at=observed_at,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        try:
            with self.session.begin_nested():
                self.session.add(model)
                self.session.flush()
            return model
        except IntegrityError:
            existing = self.find_import_by_idempotency(owner_user_id, idempotency_key)
            if existing is None:
                raise
            return existing

    def get_import(self, import_id: UUID) -> PortfolioImportModel | None:
        return self.session.get(PortfolioImportModel, import_id)

    def get_snapshot_by_import(self, import_id: UUID) -> PortfolioSnapshotModel | None:
        return self.session.scalar(
            select(PortfolioSnapshotModel).where(PortfolioSnapshotModel.import_id == import_id)
        )

    def confirm_import(
        self,
        *,
        import_model: PortfolioImportModel,
        free_cash: Decimal,
        monthly_contribution: Decimal,
        positions: list[PortfolioPositionInput],
    ) -> PortfolioSnapshotModel:
        now = datetime.now(UTC)
        invested = sum((item.market_value for item in positions), Decimal("0"))
        snapshot = PortfolioSnapshotModel(
            owner_user_id=import_model.owner_user_id,
            import_id=import_model.id,
            brokerage=import_model.brokerage,
            observed_at=import_model.observed_at,
            currency="RUB",
            free_cash=free_cash,
            monthly_contribution=monthly_contribution,
            total_value=invested + free_cash,
            created_at=now,
        )
        self.session.add(snapshot)
        self.session.flush()
        for item in positions:
            self.session.add(
                PortfolioPositionModel(
                    snapshot_id=snapshot.id,
                    instrument_name=item.instrument_name,
                    ticker=item.ticker,
                    isin=item.isin,
                    instrument_type=str(item.instrument_type),
                    risk_bucket=str(item.risk_bucket),
                    currency="RUB",
                    quantity=item.quantity,
                    market_price=item.market_price,
                    market_value=item.market_value,
                    average_price=item.average_price,
                    nominal=item.nominal,
                    accrued_interest=item.accrued_interest,
                    coupon_rate=item.coupon_rate,
                    maturity_date=item.maturity_date,
                    tax_account_type=str(item.tax_account_type),
                    holding_started_at=item.holding_started_at,
                    estimated_fee_rate=item.estimated_fee_rate,
                )
            )
        import_model.status = "confirmed"
        import_model.confirmed_at = now
        import_model.updated_at = now
        self.session.flush()
        return snapshot

    def get_snapshot(self, snapshot_id: UUID) -> PortfolioSnapshotModel | None:
        return self.session.get(PortfolioSnapshotModel, snapshot_id)

    def list_snapshots(self, owner_user_id: UUID) -> list[PortfolioSnapshotModel]:
        return list(
            self.session.scalars(
                select(PortfolioSnapshotModel)
                .where(PortfolioSnapshotModel.owner_user_id == owner_user_id)
                .order_by(PortfolioSnapshotModel.observed_at.desc())
            )
        )

    def positions(self, snapshot_id: UUID) -> list[PortfolioPositionModel]:
        return list(
            self.session.scalars(
                select(PortfolioPositionModel)
                .where(PortfolioPositionModel.snapshot_id == snapshot_id)
                .order_by(PortfolioPositionModel.instrument_name, PortfolioPositionModel.id)
            )
        )

    def find_job_by_idempotency(
        self, owner_user_id: UUID, idempotency_key: str
    ) -> RecommendationJobModel | None:
        return self.session.scalar(
            select(RecommendationJobModel).where(
                RecommendationJobModel.owner_user_id == owner_user_id,
                RecommendationJobModel.idempotency_key == idempotency_key,
            )
        )

    def create_job(
        self,
        *,
        owner_user_id: UUID,
        idempotency_key: str,
        request_hash: str,
        snapshots: list[PortfolioSnapshotModel],
        analysis_package: dict[str, Any],
    ) -> RecommendationJobModel:
        now = datetime.now(UTC)
        job = RecommendationJobModel(
            owner_user_id=owner_user_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="queued",
            attempt_count=1,
            created_at=now,
            updated_at=now,
        )
        try:
            with self.session.begin_nested():
                self.session.add(job)
                self.session.flush()
        except IntegrityError:
            existing = self.find_job_by_idempotency(owner_user_id, idempotency_key)
            if existing is None:
                raise
            return existing
        for snapshot in snapshots:
            self.session.add(RecommendationJobSnapshotModel(job_id=job.id, snapshot_id=snapshot.id))
        self.enqueue_job(job, analysis_package)
        self.session.flush()
        return job

    def enqueue_job(self, job: RecommendationJobModel, analysis_package: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        self.session.add(
            OutboxEvent(
                id=uuid4(),
                event_type="investment.recommendation.requested.v1",
                aggregate_type="recommendation_job",
                aggregate_id=job.id,
                scope_type="personal",
                owner_user_id=job.owner_user_id,
                household_id=None,
                membership_version=None,
                payload_safe=analysis_package,
                status="pending",
                created_at=now,
                available_at=now,
                processed_at=None,
                attempt_count=job.attempt_count - 1,
                deduplication_key=f"investment-recommendation:{job.id}:attempt:{job.attempt_count}",
            )
        )

    def enqueue_ready_notification(
        self, job: RecommendationJobModel, report: RecommendationReportModel
    ) -> None:
        now = datetime.now(UTC)
        self.session.add(
            OutboxEvent(
                id=uuid4(),
                event_type="investment.recommendation.ready.v1",
                aggregate_type="recommendation_report",
                aggregate_id=report.id,
                scope_type="personal",
                owner_user_id=job.owner_user_id,
                household_id=None,
                membership_version=None,
                payload_safe={
                    "schemaVersion": 1,
                    "jobId": str(job.id),
                    "reportId": str(report.id),
                    "notification": {
                        "title": "Finance",
                        "body": "Анализ портфеля готов",
                    },
                },
                status="pending",
                created_at=now,
                available_at=now,
                processed_at=None,
                attempt_count=0,
                deduplication_key=f"investment-recommendation:{job.id}:ready",
            )
        )

    def get_job(self, job_id: UUID) -> RecommendationJobModel | None:
        return self.session.get(RecommendationJobModel, job_id)

    def get_job_for_update(self, job_id: UUID) -> RecommendationJobModel | None:
        return self.session.scalar(
            select(RecommendationJobModel)
            .where(RecommendationJobModel.id == job_id)
            .with_for_update()
        )

    def conditional_update_job(
        self,
        *,
        job_id: UUID,
        expected_version: int,
        values: dict[str, Any],
    ) -> RecommendationJobModel | None:
        result = self.session.execute(
            update(RecommendationJobModel)
            .where(
                RecommendationJobModel.id == job_id,
                RecommendationJobModel.version == expected_version,
            )
            .values(**values, version=expected_version + 1)
        )
        if result.rowcount != 1:
            return None
        self.session.flush()
        self.session.expire_all()
        return self.get_job_for_update(job_id)

    def job_snapshot_ids(self, job_id: UUID) -> list[UUID]:
        return list(
            self.session.scalars(
                select(RecommendationJobSnapshotModel.snapshot_id)
                .where(RecommendationJobSnapshotModel.job_id == job_id)
                .order_by(RecommendationJobSnapshotModel.snapshot_id)
            )
        )

    def nonce_exists(self, nonce: str) -> bool:
        return (
            self.session.scalar(
                select(RecommendationCallbackNonceModel.id).where(
                    RecommendationCallbackNonceModel.nonce == nonce
                )
            )
            is not None
        )

    def record_nonce(
        self, *, job_id: UUID, nonce: str, received_at: datetime, expires_at: datetime
    ) -> bool:
        try:
            with self.session.begin_nested():
                self.session.add(
                    RecommendationCallbackNonceModel(
                        job_id=job_id,
                        nonce=nonce,
                        received_at=received_at,
                        expires_at=expires_at,
                    )
                )
                self.session.flush()
            return True
        except IntegrityError:
            return False

    def save_report(
        self,
        *,
        job: RecommendationJobModel,
        summary: str,
        assumptions: dict[str, Any],
        generated_at: datetime,
        valid_until: datetime,
        disclaimer: str,
        actions: list[RecommendationActionInput],
        sources: list[ValidatedRecommendationSource],
    ) -> RecommendationReportModel:
        report = RecommendationReportModel(
            owner_user_id=job.owner_user_id,
            job_id=job.id,
            summary=summary,
            assumptions=assumptions,
            generated_at=generated_at,
            valid_until=valid_until,
            disclaimer=disclaimer,
        )
        self.session.add(report)
        self.session.flush()
        for item in actions:
            self.session.add(
                RecommendationActionModel(
                    report_id=report.id,
                    instrument_name=item.instrument_name,
                    ticker=item.ticker,
                    isin=item.isin,
                    risk_bucket=str(item.risk_bucket),
                    action=str(item.action),
                    current_percent=item.current_percent,
                    target_percent=item.target_percent,
                    amount=item.amount,
                    priority=item.priority,
                    rationale=item.rationale,
                    risks=item.risks,
                )
            )
        for validated in sources:
            item = validated.source
            self.session.add(
                RecommendationSourceModel(
                    report_id=report.id,
                    title=item.title,
                    url=str(item.url),
                    publisher=item.publisher,
                    trust_tier=validated.trust_tier,
                    published_at=item.published_at,
                    fetched_at=item.fetched_at,
                )
            )
        self.session.flush()
        return report

    def report_for_job(self, job_id: UUID) -> RecommendationReportModel | None:
        return self.session.scalar(
            select(RecommendationReportModel).where(RecommendationReportModel.job_id == job_id)
        )

    def report_actions(self, report_id: UUID) -> list[RecommendationActionModel]:
        return list(
            self.session.scalars(
                select(RecommendationActionModel)
                .where(RecommendationActionModel.report_id == report_id)
                .order_by(RecommendationActionModel.priority, RecommendationActionModel.id)
            )
        )

    def report_sources(self, report_id: UUID) -> list[RecommendationSourceModel]:
        return list(
            self.session.scalars(
                select(RecommendationSourceModel)
                .where(RecommendationSourceModel.report_id == report_id)
                .order_by(RecommendationSourceModel.publisher, RecommendationSourceModel.id)
            )
        )


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()
