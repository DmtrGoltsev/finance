from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

MONEY_QUANTUM = Decimal("0.0001")
PERCENT_HUNDRED = Decimal("100")


class RiskBucket(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


BUCKET_ORDER = (
    RiskBucket.CONSERVATIVE,
    RiskBucket.MODERATE,
    RiskBucket.AGGRESSIVE,
)


@dataclass(frozen=True, slots=True)
class AllocationPolicy:
    conservative: Decimal = Decimal("40")
    moderate: Decimal = Decimal("30")
    aggressive: Decimal = Decimal("30")
    tolerance: Decimal = Decimal("5")

    def target_for(self, bucket: RiskBucket) -> Decimal:
        return {
            RiskBucket.CONSERVATIVE: self.conservative,
            RiskBucket.MODERATE: self.moderate,
            RiskBucket.AGGRESSIVE: self.aggressive,
        }[bucket]

    def validate(self) -> None:
        values = (self.conservative, self.moderate, self.aggressive)
        if any(value < 0 for value in values):
            raise ValueError("allocation percentages must be non-negative")
        if sum(values) != PERCENT_HUNDRED:
            raise ValueError("allocation percentages must total 100")
        if self.tolerance < 0 or self.tolerance > 25:
            raise ValueError("tolerance must be between 0 and 25")


@dataclass(frozen=True, slots=True)
class BucketAdjustment:
    bucket: RiskBucket
    add_amount: Decimal
    reduce_amount: Decimal
    current_percent: Decimal
    projected_percent: Decimal
    target_percent: Decimal
    within_tolerance: bool


def cash_first_rebalance(
    *,
    current_values: dict[RiskBucket, Decimal],
    free_cash: Decimal,
    monthly_contribution: Decimal,
    policy: AllocationPolicy | None = None,
) -> list[BucketAdjustment]:
    """Allocate new money before proposing reductions from overweight buckets.

    The result is deterministic: ties are resolved in conservative, moderate,
    aggressive order. It is a calculation boundary, not investment advice and
    never executes trades.
    """

    policy = policy or AllocationPolicy()
    policy.validate()
    normalized = {
        bucket: max(Decimal("0"), current_values.get(bucket, Decimal("0")))
        for bucket in BUCKET_ORDER
    }
    cash = max(Decimal("0"), free_cash) + max(Decimal("0"), monthly_contribution)
    invested = sum(normalized.values(), Decimal("0"))
    projected_total = invested + cash
    if projected_total <= 0:
        return [
            BucketAdjustment(
                bucket=bucket,
                add_amount=Decimal("0"),
                reduce_amount=Decimal("0"),
                current_percent=Decimal("0"),
                projected_percent=Decimal("0"),
                target_percent=policy.target_for(bucket),
                within_tolerance=False,
            )
            for bucket in BUCKET_ORDER
        ]

    target_amounts = {
        bucket: _money(projected_total * policy.target_for(bucket) / PERCENT_HUNDRED)
        for bucket in BUCKET_ORDER
    }
    additions = {bucket: Decimal("0") for bucket in BUCKET_ORDER}
    reductions = {bucket: Decimal("0") for bucket in BUCKET_ORDER}

    remaining_cash = cash
    for bucket in BUCKET_ORDER:
        deficit = max(Decimal("0"), target_amounts[bucket] - normalized[bucket])
        addition = min(deficit, remaining_cash)
        additions[bucket] = _money(addition)
        remaining_cash -= addition

    projected = {bucket: normalized[bucket] + additions[bucket] for bucket in BUCKET_ORDER}

    if remaining_cash > 0:
        # All deficits are filled; rounding residue goes to the first bucket.
        additions[RiskBucket.CONSERVATIVE] = _money(
            additions[RiskBucket.CONSERVATIVE] + remaining_cash
        )
        projected[RiskBucket.CONSERVATIVE] += remaining_cash
        remaining_cash = Decimal("0")

    unresolved_deficits = {
        bucket: max(Decimal("0"), target_amounts[bucket] - projected[bucket])
        for bucket in BUCKET_ORDER
    }
    total_deficit = sum(unresolved_deficits.values(), Decimal("0"))
    if total_deficit > 0:
        for source in BUCKET_ORDER:
            upper = (
                projected_total * (policy.target_for(source) + policy.tolerance) / PERCENT_HUNDRED
            )
            available = max(Decimal("0"), projected[source] - upper)
            reduction = min(available, total_deficit)
            if reduction <= 0:
                continue
            reductions[source] = _money(reduction)
            projected[source] -= reduction
            total_deficit -= reduction
            for destination in BUCKET_ORDER:
                need = unresolved_deficits[destination]
                if need <= 0 or reduction <= 0:
                    continue
                moved = min(need, reduction)
                additions[destination] = _money(additions[destination] + moved)
                projected[destination] += moved
                unresolved_deficits[destination] -= moved
                reduction -= moved

    result: list[BucketAdjustment] = []
    for bucket in BUCKET_ORDER:
        current_percent = _percent(normalized[bucket], invested)
        projected_percent = _percent(projected[bucket], projected_total)
        target = policy.target_for(bucket)
        result.append(
            BucketAdjustment(
                bucket=bucket,
                add_amount=_money(additions[bucket]),
                reduce_amount=_money(reductions[bucket]),
                current_percent=current_percent,
                projected_percent=projected_percent,
                target_percent=target,
                within_tolerance=abs(projected_percent - target) <= policy.tolerance,
            )
        )
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _percent(value: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal("0")
    return (value * PERCENT_HUNDRED / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
