"""Canonical backend domain enums aligned with the public API contract."""

from __future__ import annotations

from enum import Enum
from typing import Final


class DomainStrEnum(str, Enum):
    """String enum base that serializes cleanly in Pydantic and JSON."""

    def __str__(self) -> str:
        return self.value


class OwnershipType(DomainStrEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class AccountType(DomainStrEnum):
    CASH = "cash"
    BANK = "bank"
    CARD = "card"
    DEPOSIT = "deposit"
    BROKERAGE = "brokerage"
    METAL = "metal"
    OTHER = "other"


class CategoryScope(DomainStrEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class CategoryType(DomainStrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionType(DomainStrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    BROKERAGE = "brokerage"
    ASSET_BUY = "asset_buy"
    ASSET_SELL = "asset_sell"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    ADJUSTMENT = "adjustment"


class ReportMode(DomainStrEnum):
    PERSONAL = "personal"
    SHARED_FAMILY_REPORT = "shared_family_report"
    COMBINED_VIEWER_OVERVIEW = "combined_viewer_overview"


class TransferScope(DomainStrEnum):
    PERSONAL_SAME_OWNER = "personal_same_owner"
    HOUSEHOLD_SAME_HOUSEHOLD = "household_same_household"
    UNSUPPORTED_CROSS_SCOPE = "unsupported_cross_scope"


class SourceType(DomainStrEnum):
    MANUAL = "manual"


RESERVED_POST_MVP_SOURCE_TYPES: Final[frozenset[str]] = frozenset(
    {"file_import", "bank_api", "sms", "push"}
)


class RecordStatus(DomainStrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MembershipStatus(DomainStrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REVOKED = "revoked"


class InviteStatus(DomainStrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


def validate_mvp_source_type_for_write(value: SourceType | str) -> SourceType:
    """Return the MVP source type accepted by create/update flows.

    Post-MVP source values are reserved vocabulary only; accepting them here
    would imply file import, bank API, SMS, or push ingestion support.
    """

    raw_value = value.value if isinstance(value, SourceType) else value
    if raw_value == SourceType.MANUAL.value:
        return SourceType.MANUAL
    if raw_value in RESERVED_POST_MVP_SOURCE_TYPES:
        raise ValueError(f"sourceType '{raw_value}' is reserved for post-MVP use")
    raise ValueError(f"unsupported sourceType '{raw_value}'")
