try:
    from app.authz import (
        Account,
        AccountOwnershipType,
        Actor,
        Category,
        CategoryKind,
        CategoryScope,
        DenialReason,
        ExportRequest,
        HouseholdRef,
        Invite,
        Membership,
        MembershipStatus,
        ReportMode,
        ReportRequest,
        ResourceStatus,
        ScopeRef,
        Transaction,
        TransactionDraft,
        TransactionType,
        TransferScopeKind,
        canAcceptInvite,
        canCreateTransaction,
        canExportData,
        canLeaveHousehold,
        canManageInvite,
        canMutateAccount,
        canMutateCategory,
        canMutateTransaction,
        canReadAccount,
        canReadCategory,
        canReadReport,
        canReadTransaction,
        canUseCategory,
        canUseTransferScope,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "fastapi"}:
        raise

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "app"))

    from authz import (
        Account,
        AccountOwnershipType,
        Actor,
        Category,
        CategoryKind,
        CategoryScope,
        DenialReason,
        ExportRequest,
        HouseholdRef,
        Invite,
        Membership,
        MembershipStatus,
        ReportMode,
        ReportRequest,
        ResourceStatus,
        ScopeRef,
        Transaction,
        TransactionDraft,
        TransactionType,
        TransferScopeKind,
        canAcceptInvite,
        canCreateTransaction,
        canExportData,
        canLeaveHousehold,
        canManageInvite,
        canMutateAccount,
        canMutateCategory,
        canMutateTransaction,
        canReadAccount,
        canReadCategory,
        canReadReport,
        canReadTransaction,
        canUseCategory,
        canUseTransferScope,
    )


OWNER_A = "owner-a"
MEMBER_B = "member-b"
OTHER_C = "other-c"
INVITED = "invited-ab"
FORMER = "former-ab"
HH_AB = "household-ab"
HH_C = "household-c"


def actor(user_id, status_by_household=()):
    return Actor(
        user_id=user_id,
        memberships=tuple(
            Membership(user_id=user_id, household_id=household_id, status=status)
            for household_id, status in status_by_household
        ),
    )


owner_a = actor(OWNER_A, ((HH_AB, MembershipStatus.ACTIVE),))
member_b = actor(MEMBER_B, ((HH_AB, MembershipStatus.ACTIVE),))
other_c = actor(OTHER_C, ((HH_C, MembershipStatus.ACTIVE),))
invited_ab = actor(INVITED, ((HH_AB, MembershipStatus.INVITED),))
former_ab = actor(FORMER, ((HH_AB, MembershipStatus.LEFT),))

personal_a = Account(
    id="account-personal-a",
    ownership_type=AccountOwnershipType.PERSONAL,
    owner_user_id=OWNER_A,
)
personal_a_2 = Account(
    id="account-personal-a-2",
    ownership_type=AccountOwnershipType.PERSONAL,
    owner_user_id=OWNER_A,
)
personal_b = Account(
    id="account-personal-b",
    ownership_type=AccountOwnershipType.PERSONAL,
    owner_user_id=MEMBER_B,
)
shared_ab = Account(
    id="account-shared-ab",
    ownership_type=AccountOwnershipType.SHARED,
    household_id=HH_AB,
)
shared_ab_2 = Account(
    id="account-shared-ab-2",
    ownership_type=AccountOwnershipType.SHARED,
    household_id=HH_AB,
)
shared_c = Account(
    id="account-shared-c",
    ownership_type=AccountOwnershipType.SHARED,
    household_id=HH_C,
)

personal_category_a = Category(
    id="category-personal-a",
    scope=CategoryScope.PERSONAL,
    owner_user_id=OWNER_A,
    kind=CategoryKind.EXPENSE,
)
household_category_ab = Category(
    id="category-household-ab",
    scope=CategoryScope.HOUSEHOLD,
    household_id=HH_AB,
    kind=CategoryKind.EXPENSE,
)
household_category_c = Category(
    id="category-household-c",
    scope=CategoryScope.HOUSEHOLD,
    household_id=HH_C,
)


def assert_denied(decision):
    assert not decision.allowed
    assert decision.reason is not None


def test_account_predicates_enforce_owner_only_and_active_shared_access():
    assert canReadAccount(owner_a, personal_a).allowed
    assert canMutateAccount(owner_a, personal_a).allowed

    assert_denied(canReadAccount(member_b, personal_a))
    assert_denied(canReadAccount(other_c, personal_a))

    assert canReadAccount(owner_a, shared_ab).allowed
    assert canReadAccount(member_b, shared_ab).allowed
    assert canMutateAccount(member_b, shared_ab).allowed

    assert_denied(canReadAccount(other_c, shared_ab))
    assert_denied(canReadAccount(invited_ab, shared_ab))
    assert_denied(canReadAccount(former_ab, shared_ab))

    archived_shared = Account(
        id="account-shared-ab-archived",
        ownership_type=AccountOwnershipType.SHARED,
        household_id=HH_AB,
        status=ResourceStatus.ARCHIVED,
    )
    mutation = canMutateAccount(owner_a, archived_shared)
    assert not mutation.allowed
    assert mutation.reason == DenialReason.ARCHIVED_RECORD_NOT_MUTABLE

    ownership_change = canMutateAccount(
        owner_a,
        personal_a,
        proposed_ownership_type=AccountOwnershipType.SHARED,
    )
    assert not ownership_change.allowed
    assert ownership_change.reason == DenialReason.ACCOUNT_OWNERSHIP_IMMUTABLE


def test_report_scope_resolver_covers_shared_and_combined_modes():
    personal_report = canReadReport(
        owner_a,
        ReportRequest(mode=ReportMode.PERSONAL, household_id=None),
    )
    assert personal_report.allowed
    assert personal_report.visible_scope is not None
    assert personal_report.visible_scope.scopes == (ScopeRef.personal(OWNER_A),)
    assert personal_report.resolved_scope == ScopeRef.personal(OWNER_A)

    shared_report = canReadReport(
        owner_a,
        ReportRequest(mode=ReportMode.SHARED_FAMILY_REPORT, household_id=HH_AB),
    )
    assert shared_report.allowed
    assert shared_report.visible_scope is not None
    assert shared_report.visible_scope.scopes == (ScopeRef.household(HH_AB),)

    combined_report = canReadReport(
        owner_a,
        ReportRequest(mode=ReportMode.COMBINED_VIEWER_OVERVIEW, household_id=HH_AB),
    )
    assert combined_report.allowed
    assert combined_report.visible_scope is not None
    assert combined_report.visible_scope.scopes == (
        ScopeRef.household(HH_AB),
        ScopeRef.personal(OWNER_A),
    )

    member_combined = canReadReport(
        member_b,
        ReportRequest(mode=ReportMode.COMBINED_VIEWER_OVERVIEW, household_id=HH_AB),
    )
    assert member_combined.allowed
    assert member_combined.visible_scope is not None
    assert ScopeRef.personal(MEMBER_B) in member_combined.visible_scope.scopes
    assert ScopeRef.personal(OWNER_A) not in member_combined.visible_scope.scopes

    exported = canExportData(
        owner_a,
        ExportRequest(mode=ReportMode.COMBINED_VIEWER_OVERVIEW, household_id=HH_AB),
    )
    assert exported.allowed
    assert exported.visible_scope == combined_report.visible_scope

    personal_export = canExportData(
        owner_a,
        ExportRequest(mode=ReportMode.PERSONAL, household_id=None),
    )
    assert personal_export.allowed
    assert personal_export.visible_scope == personal_report.visible_scope

    assert_denied(
        canReadReport(
            invited_ab,
            ReportRequest(mode=ReportMode.SHARED_FAMILY_REPORT, household_id=HH_AB),
        )
    )
    assert_denied(
        canReadReport(
            former_ab,
            ReportRequest(mode=ReportMode.COMBINED_VIEWER_OVERVIEW, household_id=HH_AB),
        )
    )
    assert_denied(
        canReadReport(
            other_c,
            ReportRequest(mode=ReportMode.SHARED_FAMILY_REPORT, household_id=HH_AB),
        )
    )


def test_transfer_scope_allows_only_personal_same_owner_or_same_household():
    personal_transfer = canUseTransferScope(owner_a, personal_a, personal_a_2)
    assert personal_transfer.allowed
    assert personal_transfer.transfer_scope == TransferScopeKind.PERSONAL_SAME_OWNER
    assert personal_transfer.resolved_scope == ScopeRef.personal(OWNER_A)

    shared_transfer = canUseTransferScope(member_b, shared_ab, shared_ab_2)
    assert shared_transfer.allowed
    assert shared_transfer.transfer_scope == TransferScopeKind.HOUSEHOLD_SAME_HOUSEHOLD
    assert shared_transfer.resolved_scope == ScopeRef.household(HH_AB)

    mixed_transfer = canUseTransferScope(owner_a, personal_a, shared_ab)
    assert not mixed_transfer.allowed
    assert mixed_transfer.reason == DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED

    cross_user_personal = canUseTransferScope(owner_a, personal_a, personal_b)
    assert not cross_user_personal.allowed
    assert cross_user_personal.reason == DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED

    cross_household_shared = canUseTransferScope(owner_a, shared_ab, shared_c)
    assert not cross_household_shared.allowed
    assert cross_household_shared.reason == DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED

    assert_denied(canUseTransferScope(invited_ab, shared_ab, shared_ab_2))
    assert_denied(canUseTransferScope(former_ab, shared_ab, shared_ab_2))


def test_transaction_predicates_inherit_account_and_transfer_boundaries():
    personal_expense = Transaction(
        id="tx-personal-a",
        transaction_type=TransactionType.EXPENSE,
        account=personal_a,
        category=personal_category_a,
    )
    shared_transfer = Transaction(
        id="tx-shared-transfer-ab",
        transaction_type=TransactionType.TRANSFER,
        account=shared_ab,
        counterparty_account=shared_ab_2,
    )

    assert canReadTransaction(owner_a, personal_expense).allowed
    assert canMutateTransaction(owner_a, personal_expense).allowed
    assert_denied(canReadTransaction(member_b, personal_expense))

    assert canReadTransaction(owner_a, shared_transfer).allowed
    assert canMutateTransaction(member_b, shared_transfer).allowed
    assert_denied(canReadTransaction(invited_ab, shared_transfer))
    assert_denied(canReadTransaction(former_ab, shared_transfer))

    allowed_draft = TransactionDraft(
        transaction_type=TransactionType.EXPENSE,
        account=shared_ab,
        category=household_category_ab,
    )
    assert canCreateTransaction(member_b, allowed_draft).allowed

    hidden_account_draft = TransactionDraft(
        transaction_type=TransactionType.EXPENSE,
        account=personal_a,
        category=personal_category_a,
    )
    hidden_account_decision = canCreateTransaction(member_b, hidden_account_draft)
    assert not hidden_account_decision.allowed
    assert (
        hidden_account_decision.reason
        == DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE
    )

    mixed_transfer_draft = TransactionDraft(
        transaction_type=TransactionType.TRANSFER,
        account=personal_a,
        counterparty_account=shared_ab,
    )
    mixed_transfer_decision = canCreateTransaction(owner_a, mixed_transfer_draft)
    assert not mixed_transfer_decision.allowed
    assert mixed_transfer_decision.reason == DenialReason.TRANSFER_SCOPE_NOT_SUPPORTED


def test_category_invite_and_household_membership_predicates():
    assert canReadCategory(owner_a, personal_category_a).allowed
    assert canMutateCategory(owner_a, personal_category_a).allowed
    assert_denied(canReadCategory(member_b, personal_category_a))

    assert canReadCategory(owner_a, household_category_ab).allowed
    assert canReadCategory(member_b, household_category_ab).allowed
    assert canMutateCategory(member_b, household_category_ab).allowed
    assert_denied(canReadCategory(invited_ab, household_category_ab))
    assert_denied(canReadCategory(former_ab, household_category_ab))

    assert canUseCategory(
        owner_a,
        personal_category_a,
        personal_a,
        transaction_type=TransactionType.EXPENSE,
    ).allowed
    assert canUseCategory(
        member_b,
        household_category_ab,
        shared_ab,
        transaction_type=TransactionType.EXPENSE,
    ).allowed

    cross_scope_category = canUseCategory(
        owner_a,
        household_category_ab,
        personal_a,
        transaction_type=TransactionType.EXPENSE,
    )
    assert not cross_scope_category.allowed
    assert (
        cross_scope_category.reason
        == DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE
    )

    foreign_category = canUseCategory(
        owner_a,
        household_category_c,
        shared_ab,
        transaction_type=TransactionType.EXPENSE,
    )
    assert not foreign_category.allowed
    assert (
        foreign_category.reason
        == DenialReason.REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE
    )

    household = HouseholdRef(household_id=HH_AB)
    assert canManageInvite(owner_a, household).allowed
    assert canManageInvite(member_b, household).allowed
    assert_denied(canManageInvite(invited_ab, household))
    assert_denied(canManageInvite(former_ab, household))

    invite = Invite(
        id="invite-ab",
        household_id=HH_AB,
        invited_user_id=INVITED,
        token_verified=True,
    )
    assert canAcceptInvite(invited_ab, invite).allowed
    assert_denied(canAcceptInvite(owner_a, invite))

    assert canLeaveHousehold(owner_a, household).allowed
    assert canLeaveHousehold(member_b, household).allowed
    assert_denied(canLeaveHousehold(invited_ab, household))
    assert_denied(canLeaveHousehold(former_ab, household))
