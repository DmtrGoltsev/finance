from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple, Union


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Decision(StringEnum):
    ALLOW = "allow"
    DENY = "deny"


class DenialReason(StringEnum):
    UNAUTHENTICATED = "unauthenticated"
    RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE = "resource_not_found_or_not_accessible"
    REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE = (
        "referenced_resource_not_found_or_not_accessible"
    )
    INVITE_NOT_FOUND_OR_NOT_ACCESSIBLE = "invite_not_found_or_not_accessible"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    TRANSFER_SCOPE_NOT_SUPPORTED = "transfer_scope_not_supported"
    ACCOUNT_OWNERSHIP_IMMUTABLE = "account_ownership_immutable"
    ARCHIVED_RECORD_NOT_MUTABLE = "archived_record_not_mutable"
    VALIDATION_FAILED = "validation_failed"


class AuditClass(StringEnum):
    NO_AUDIT = "no_audit"
    AUDIT_ALLOW = "audit_allow"
    AUDIT_DENY = "audit_deny"
    AUDIT_STATE_DENY = "audit_state_deny"


class ScopeKind(StringEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class MembershipStatus(StringEnum):
    INVITED = "invited"
    ACTIVE = "active"
    LEFT = "left"
    REVOKED = "revoked"


class AccountOwnershipType(StringEnum):
    PERSONAL = "personal"
    SHARED = "shared"


class CategoryScope(StringEnum):
    PERSONAL = "personal"
    HOUSEHOLD = "household"


class CategoryKind(StringEnum):
    INCOME = "income"
    EXPENSE = "expense"
    BOTH = "both"


class ResourceStatus(StringEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class TransactionType(StringEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    BROKERAGE = "brokerage"


class SourceType(StringEnum):
    MANUAL = "manual"


class ReportMode(StringEnum):
    SHARED_FAMILY_REPORT = "shared_family_report"
    COMBINED_VIEWER_OVERVIEW = "combined_viewer_overview"


class InviteStatus(StringEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TransferScopeKind(StringEnum):
    PERSONAL_SAME_OWNER = "personal_same_owner"
    HOUSEHOLD_SAME_HOUSEHOLD = "household_same_household"


@dataclass(frozen=True)
class ScopeRef:
    kind: ScopeKind
    id: str

    @classmethod
    def personal(cls, owner_user_id: str) -> "ScopeRef":
        return cls(kind=ScopeKind.PERSONAL, id=owner_user_id)

    @classmethod
    def household(cls, household_id: str) -> "ScopeRef":
        return cls(kind=ScopeKind.HOUSEHOLD, id=household_id)


@dataclass(frozen=True)
class Membership:
    user_id: str
    household_id: str
    status: MembershipStatus


@dataclass(frozen=True)
class Actor:
    user_id: Optional[str]
    memberships: Sequence[Membership] = ()
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    @classmethod
    def anonymous(cls) -> "Actor":
        return cls(user_id=None)


@dataclass(frozen=True)
class HouseholdRef:
    household_id: str


@dataclass(frozen=True)
class Account:
    id: str
    ownership_type: AccountOwnershipType
    owner_user_id: Optional[str] = None
    household_id: Optional[str] = None
    status: ResourceStatus = ResourceStatus.ACTIVE


@dataclass(frozen=True)
class Category:
    id: str
    scope: CategoryScope
    owner_user_id: Optional[str] = None
    household_id: Optional[str] = None
    kind: CategoryKind = CategoryKind.BOTH
    status: ResourceStatus = ResourceStatus.ACTIVE


@dataclass(frozen=True)
class Transaction:
    id: str
    transaction_type: TransactionType
    account: Account
    counterparty_account: Optional[Account] = None
    category: Optional[Category] = None
    source_type: SourceType = SourceType.MANUAL
    status: ResourceStatus = ResourceStatus.ACTIVE


@dataclass(frozen=True)
class TransactionDraft:
    transaction_type: TransactionType
    account: Account
    counterparty_account: Optional[Account] = None
    category: Optional[Category] = None
    source_type: SourceType = SourceType.MANUAL


@dataclass(frozen=True)
class ReportRequest:
    mode: ReportMode
    household_id: Optional[str]


@dataclass(frozen=True)
class ExportRequest:
    mode: ReportMode
    household_id: Optional[str]


@dataclass(frozen=True)
class Invite:
    id: str
    household_id: str
    invited_user_id: str
    status: InviteStatus = InviteStatus.PENDING
    token_verified: bool = False


@dataclass(frozen=True)
class VisibleReportScope:
    mode: ReportMode
    scopes: Tuple[ScopeRef, ...]

    @property
    def household_scopes(self) -> Tuple[ScopeRef, ...]:
        return tuple(scope for scope in self.scopes if scope.kind == ScopeKind.HOUSEHOLD)

    @property
    def personal_scopes(self) -> Tuple[ScopeRef, ...]:
        return tuple(scope for scope in self.scopes if scope.kind == ScopeKind.PERSONAL)


@dataclass(frozen=True)
class AuthzDecision:
    decision: Decision
    reason: Optional[DenialReason] = None
    resolved_scope: Optional[ScopeRef] = None
    visible_scope: Optional[VisibleReportScope] = None
    transfer_scope: Optional[TransferScopeKind] = None
    audit: AuditClass = AuditClass.NO_AUDIT

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW

    def __bool__(self) -> bool:
        return self.allowed


def allow(
    *,
    resolved_scope: Optional[ScopeRef] = None,
    visible_scope: Optional[VisibleReportScope] = None,
    transfer_scope: Optional[TransferScopeKind] = None,
    audit: AuditClass = AuditClass.AUDIT_ALLOW,
) -> AuthzDecision:
    return AuthzDecision(
        decision=Decision.ALLOW,
        reason=None,
        resolved_scope=resolved_scope,
        visible_scope=visible_scope,
        transfer_scope=transfer_scope,
        audit=audit,
    )


def deny(
    reason: DenialReason = DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE,
    *,
    audit: AuditClass = AuditClass.AUDIT_DENY,
) -> AuthzDecision:
    return AuthzDecision(decision=Decision.DENY, reason=reason, audit=audit)


def _is_authenticated(actor: Actor) -> bool:
    return bool(actor.user_id)


def _has_active_membership(actor: Actor, household_id: Optional[str]) -> bool:
    if not household_id or not actor.user_id:
        return False

    return any(
        membership.user_id == actor.user_id
        and membership.household_id == household_id
        and membership.status == MembershipStatus.ACTIVE
        for membership in actor.memberships
    )


def _account_scope(account: Account) -> Optional[ScopeRef]:
    if account.status == ResourceStatus.DELETED:
        return None

    if account.ownership_type == AccountOwnershipType.PERSONAL and account.owner_user_id:
        return ScopeRef.personal(account.owner_user_id)

    if account.ownership_type == AccountOwnershipType.SHARED and account.household_id:
        return ScopeRef.household(account.household_id)

    return None


def _category_scope(category: Category) -> Optional[ScopeRef]:
    if category.status == ResourceStatus.DELETED:
        return None

    if category.scope == CategoryScope.PERSONAL and category.owner_user_id:
        return ScopeRef.personal(category.owner_user_id)

    if category.scope == CategoryScope.HOUSEHOLD and category.household_id:
        return ScopeRef.household(category.household_id)

    return None


def _reference_denial(decision: AuthzDecision) -> AuthzDecision:
    if decision.reason == DenialReason.UNAUTHENTICATED:
        return decision

    if decision.reason in {
        DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
        DenialReason.ACCOUNT_OWNERSHIP_IMMUTABLE,
        DenialReason.ACTION_NOT_ALLOWED,
    }:
        return decision

    return deny(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


def _category_supports_transaction(
    category: Category, transaction_type: Optional[TransactionType]
) -> bool:
    if transaction_type is None or transaction_type not in {
        TransactionType.INCOME,
        TransactionType.EXPENSE,
    }:
        return True

    return category.kind in {CategoryKind.BOTH, CategoryKind(transaction_type.value)}


def canReadAccount(actor: Actor, account: Account) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    scope = _account_scope(account)
    if not scope:
        return deny()

    if scope.kind == ScopeKind.PERSONAL and scope.id == actor.user_id:
        return allow(resolved_scope=scope)

    if scope.kind == ScopeKind.HOUSEHOLD and _has_active_membership(actor, scope.id):
        return allow(resolved_scope=scope)

    return deny()


def canMutateAccount(
    actor: Actor,
    account: Account,
    *,
    proposed_ownership_type: Optional[AccountOwnershipType] = None,
) -> AuthzDecision:
    read_decision = canReadAccount(actor, account)
    if not read_decision.allowed:
        return read_decision

    if (
        proposed_ownership_type is not None
        and proposed_ownership_type != account.ownership_type
    ):
        return deny(
            DenialReason.ACCOUNT_OWNERSHIP_IMMUTABLE,
            audit=AuditClass.AUDIT_STATE_DENY,
        )

    if account.status != ResourceStatus.ACTIVE:
        return deny(
            DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
            audit=AuditClass.AUDIT_STATE_DENY,
        )

    return allow(resolved_scope=read_decision.resolved_scope)


def canReadCategory(actor: Actor, category: Category) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    scope = _category_scope(category)
    if not scope:
        return deny()

    if scope.kind == ScopeKind.PERSONAL and scope.id == actor.user_id:
        return allow(resolved_scope=scope)

    if scope.kind == ScopeKind.HOUSEHOLD and _has_active_membership(actor, scope.id):
        return allow(resolved_scope=scope)

    return deny()


def canMutateCategory(actor: Actor, category: Category) -> AuthzDecision:
    read_decision = canReadCategory(actor, category)
    if not read_decision.allowed:
        return read_decision

    if category.status != ResourceStatus.ACTIVE:
        return deny(
            DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
            audit=AuditClass.AUDIT_STATE_DENY,
        )

    return allow(resolved_scope=read_decision.resolved_scope)


def canUseCategory(
    actor: Actor,
    category: Category,
    account: Account,
    *,
    transaction_type: Optional[TransactionType] = None,
) -> AuthzDecision:
    account_decision = canReadAccount(actor, account)
    if not account_decision.allowed:
        return _reference_denial(account_decision)

    category_decision = canReadCategory(actor, category)
    if not category_decision.allowed:
        return _reference_denial(category_decision)

    if not _category_supports_transaction(category, transaction_type):
        return deny(DenialReason.ACTION_NOT_ALLOWED)

    if account_decision.resolved_scope == category_decision.resolved_scope:
        return allow(resolved_scope=account_decision.resolved_scope)

    return deny(DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE)


def canUseTransferScope(
    actor: Actor, account: Account, counterparty_account: Account
) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    if (
        account.ownership_type == AccountOwnershipType.PERSONAL
        and counterparty_account.ownership_type == AccountOwnershipType.PERSONAL
        and account.owner_user_id
        and account.owner_user_id == counterparty_account.owner_user_id
        and account.owner_user_id == actor.user_id
    ):
        if (
            account.status != ResourceStatus.ACTIVE
            or counterparty_account.status != ResourceStatus.ACTIVE
        ):
            return deny(
                DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
                audit=AuditClass.AUDIT_STATE_DENY,
            )

        return allow(
            resolved_scope=ScopeRef.personal(actor.user_id),
            transfer_scope=TransferScopeKind.PERSONAL_SAME_OWNER,
        )

    if (
        account.ownership_type == AccountOwnershipType.SHARED
        and counterparty_account.ownership_type == AccountOwnershipType.SHARED
        and account.household_id
        and account.household_id == counterparty_account.household_id
        and _has_active_membership(actor, account.household_id)
    ):
        if (
            account.status != ResourceStatus.ACTIVE
            or counterparty_account.status != ResourceStatus.ACTIVE
        ):
            return deny(
                DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
                audit=AuditClass.AUDIT_STATE_DENY,
            )

        return allow(
            resolved_scope=ScopeRef.household(account.household_id),
            transfer_scope=TransferScopeKind.HOUSEHOLD_SAME_HOUSEHOLD,
        )

    return deny(DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED)


def canCreateTransaction(actor: Actor, draft: TransactionDraft) -> AuthzDecision:
    if draft.source_type != SourceType.MANUAL:
        return deny(DenialReason.ACTION_NOT_ALLOWED)

    if draft.transaction_type == TransactionType.TRANSFER:
        if draft.counterparty_account is None:
            return deny(DenialReason.VALIDATION_FAILED)

        return canUseTransferScope(actor, draft.account, draft.counterparty_account)

    account_decision = canMutateAccount(actor, draft.account)
    if not account_decision.allowed:
        return _reference_denial(account_decision)

    if draft.category is not None:
        category_decision = canUseCategory(
            actor,
            draft.category,
            draft.account,
            transaction_type=draft.transaction_type,
        )
        if not category_decision.allowed:
            return _reference_denial(category_decision)

    return allow(resolved_scope=account_decision.resolved_scope)


def canReadTransaction(actor: Actor, transaction: Transaction) -> AuthzDecision:
    if transaction.status == ResourceStatus.DELETED:
        return deny()

    if transaction.transaction_type == TransactionType.TRANSFER:
        if transaction.counterparty_account is None:
            return deny()

        transfer_decision = canUseTransferScope(
            actor, transaction.account, transaction.counterparty_account
        )
        if transfer_decision.allowed:
            return allow(resolved_scope=transfer_decision.resolved_scope)

        if transfer_decision.reason == DenialReason.UNAUTHENTICATED:
            return transfer_decision

        return deny()

    return canReadAccount(actor, transaction.account)


def canMutateTransaction(
    actor: Actor,
    transaction: Transaction,
    *,
    proposed_account: Optional[Account] = None,
    proposed_counterparty_account: Optional[Account] = None,
    proposed_category: Optional[Category] = None,
) -> AuthzDecision:
    read_decision = canReadTransaction(actor, transaction)
    if not read_decision.allowed:
        return read_decision

    if transaction.status != ResourceStatus.ACTIVE:
        return deny(
            DenialReason.ARCHIVED_RECORD_NOT_MUTABLE,
            audit=AuditClass.AUDIT_STATE_DENY,
        )

    account = proposed_account or transaction.account
    category = proposed_category if proposed_category is not None else transaction.category
    counterparty_account = (
        proposed_counterparty_account
        if proposed_counterparty_account is not None
        else transaction.counterparty_account
    )

    if transaction.transaction_type == TransactionType.TRANSFER:
        if counterparty_account is None:
            return deny(DenialReason.VALIDATION_FAILED)

        return canUseTransferScope(actor, account, counterparty_account)

    account_decision = canMutateAccount(actor, account)
    if not account_decision.allowed:
        return _reference_denial(account_decision)

    if category is not None:
        category_decision = canUseCategory(
            actor,
            category,
            account,
            transaction_type=transaction.transaction_type,
        )
        if not category_decision.allowed:
            return _reference_denial(category_decision)

    return allow(resolved_scope=account_decision.resolved_scope)


def resolveReportVisibleScope(actor: Actor, request: ReportRequest) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    if not request.household_id or not _has_active_membership(actor, request.household_id):
        return deny()

    household_scope = ScopeRef.household(request.household_id)

    if request.mode == ReportMode.SHARED_FAMILY_REPORT:
        visible_scope = VisibleReportScope(mode=request.mode, scopes=(household_scope,))
        return allow(visible_scope=visible_scope, resolved_scope=household_scope)

    if request.mode == ReportMode.COMBINED_VIEWER_OVERVIEW:
        visible_scope = VisibleReportScope(
            mode=request.mode,
            scopes=(household_scope, ScopeRef.personal(actor.user_id)),
        )
        return allow(visible_scope=visible_scope, resolved_scope=household_scope)

    return deny(DenialReason.VALIDATION_FAILED)


def canReadReport(actor: Actor, request: ReportRequest) -> AuthzDecision:
    return resolveReportVisibleScope(actor, request)


def canExportData(actor: Actor, request: ExportRequest) -> AuthzDecision:
    report_request = ReportRequest(mode=request.mode, household_id=request.household_id)
    return resolveReportVisibleScope(actor, report_request)


def canManageInvite(
    actor: Actor, target: Union[HouseholdRef, Invite]
) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    household_id = target.household_id
    if _has_active_membership(actor, household_id):
        return allow(resolved_scope=ScopeRef.household(household_id))

    return deny()


def canAcceptInvite(actor: Actor, invite: Invite) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    if (
        invite.status == InviteStatus.PENDING
        and invite.token_verified
        and invite.invited_user_id == actor.user_id
    ):
        return allow(resolved_scope=ScopeRef.household(invite.household_id))

    return deny(DenialReason.INVITE_NOT_FOUND_OR_NOT_ACCESSIBLE)


def canLeaveHousehold(actor: Actor, household: HouseholdRef) -> AuthzDecision:
    if not _is_authenticated(actor):
        return deny(DenialReason.UNAUTHENTICATED)

    if _has_active_membership(actor, household.household_id):
        return allow(resolved_scope=ScopeRef.household(household.household_id))

    return deny()
