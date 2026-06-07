"""Database enum vocabularies stored as strings plus CHECK constraints."""

from __future__ import annotations

from app.domain.enums import (
    AccountType,
    CategoryScope,
    CategoryType,
    InviteStatus,
    MembershipStatus,
    OwnershipType,
    RecordStatus,
    SourceType,
    TransactionType,
    TransferScope,
)


def values_from_enum(enum_type: type) -> tuple[str, ...]:
    return tuple(member.value for member in enum_type)


ACCOUNT_TYPES = values_from_enum(AccountType)
ASSET_CATEGORY_TYPES = ACCOUNT_TYPES
AUTH_STATUSES = ("active", "deactivated")
HOUSEHOLD_STATUSES = ("active", "archived")
RECORD_STATUSES = values_from_enum(RecordStatus)
ACTIVE_DELETED_STATUSES = ("active", "deleted")
MEMBERSHIP_STATUSES = values_from_enum(MembershipStatus)
INVITE_STATUSES = values_from_enum(InviteStatus)
OWNERSHIP_TYPES = values_from_enum(OwnershipType)
CATEGORY_SCOPES = values_from_enum(CategoryScope)
CATEGORY_TYPES = values_from_enum(CategoryType)
TRANSACTION_TYPES = values_from_enum(TransactionType)
SOURCE_TYPES = values_from_enum(SourceType)
TRANSFER_SCOPES = (
    TransferScope.PERSONAL_SAME_OWNER.value,
    TransferScope.HOUSEHOLD_SAME_HOUSEHOLD.value,
)
TRANSFER_STATUSES = ("posted", "voided")
CAPTURE_DRAFT_STATUSES = ("pending", "confirmed", "discarded")
CAPTURE_SOURCES = ("screenshot",)
SESSION_TRANSPORTS = ("cookie", "android_bearer")
SESSION_STATUSES = ("active", "revoked", "expired")
RESET_TOKEN_STATUSES = ("pending", "used", "expired", "revoked")
EXPORT_SCOPE_TYPES = ("personal", "household", "combined")
EXPORT_STATUSES = ("queued", "running", "ready", "failed", "expired", "revoked")
DELETION_REQUEST_STATUSES = ("pending", "approved", "completed", "cancelled", "rejected")
AUDIT_SCOPE_TYPES = ("personal", "household", "system")
AUDIT_RESULTS = ("allow", "deny", "state-deny", "error")
OUTBOX_STATUSES = ("pending", "processing", "processed", "failed", "dead")
PLANNING_SCOPE_TYPES = ("personal", "household")
PLANNING_INCOME_CONFIRMATION_STATES = ("planned", "confirmed")
PLANNING_ALLOCATION_TARGET_TYPES = (
    "expense_category",
    "account",
    "asset",
    "investment_asset_category",
)
PLANNING_ALLOCATION_MODES = ("amount", "percent")
