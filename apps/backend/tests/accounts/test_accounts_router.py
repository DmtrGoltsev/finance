from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.accounts.repository import AccountRecord, reset_accounts_for_tests, seed_accounts_for_tests
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import (
    AccountOwnershipType,
    Actor,
    Membership,
    MembershipStatus,
    ResourceStatus,
)
from app.main import create_app
from app.transactions.repository import (
    TransactionRecord,
    reset_transactions_for_tests,
)

OWNER_A = "owner-a"
MEMBER_B = "member-b"
OTHER_C = "other-c"
INVITED = "invited-ab"
FORMER = "former-ab"
HH_AB = "household-ab"
HH_C = "household-c"


def actor(user_id: str, memberships: tuple[tuple[str, MembershipStatus], ...] = ()) -> Actor:
    return Actor(
        user_id=user_id,
        request_id=f"req-{user_id}",
        memberships=tuple(
            Membership(user_id=user_id, household_id=household_id, status=status)
            for household_id, status in memberships
        ),
    )


ACTOR_A = actor(OWNER_A, ((HH_AB, MembershipStatus.ACTIVE),))
ACTOR_B = actor(MEMBER_B, ((HH_AB, MembershipStatus.ACTIVE),))
ACTOR_C = actor(OTHER_C, ((HH_C, MembershipStatus.ACTIVE),))
ACTOR_INVITED = actor(INVITED, ((HH_AB, MembershipStatus.INVITED),))
ACTOR_FORMER = actor(FORMER, ((HH_AB, MembershipStatus.LEFT),))


def account_record(
    account_id: str,
    name: str,
    ownership_type: AccountOwnershipType,
    *,
    owner_user_id: str | None = None,
    household_id: str | None = None,
    status: ResourceStatus = ResourceStatus.ACTIVE,
) -> AccountRecord:
    now = datetime(2026, 5, 17, 8, 0, tzinfo=UTC)
    return AccountRecord(
        id=account_id,
        name=name,
        account_type="cash",
        ownership_type=ownership_type,
        owner_user_id=owner_user_id,
        household_id=household_id,
        currency="RUB",
        initial_balance=Decimal("100.00"),
        current_balance=Decimal("100.00"),
        status=status,
        created_by_user_id=owner_user_id or "creator-shared",
        created_at=now,
        updated_at=now,
    )


def transaction_record(
    transaction_id: str,
    *,
    account_id: str,
    counterparty_account_id: str | None = None,
) -> TransactionRecord:
    now = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
    return TransactionRecord(
        id=transaction_id,
        transaction_type="expense",
        account_id=account_id,
        counterparty_account_id=counterparty_account_id,
        category_id="cat-food",
        amount=Decimal("1.00"),
        currency="RUB",
        occurred_at=now,
        description="seeded transaction",
        source_type="manual",
        transfer_scope=None,
        transfer_status=None,
        record_status="active",
        created_by_user_id=OWNER_A,
        last_edited_by_user_id=OWNER_A,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        version=1,
    )


@pytest.fixture(autouse=True)
def seeded_accounts() -> Iterator[None]:
    reset_accounts_for_tests()
    reset_transactions_for_tests()
    seed_accounts_for_tests(
        [
            account_record(
                "acct-personal-a",
                "A Wallet",
                AccountOwnershipType.PERSONAL,
                owner_user_id=OWNER_A,
            ),
            account_record(
                "acct-personal-b",
                "B Wallet",
                AccountOwnershipType.PERSONAL,
                owner_user_id=MEMBER_B,
            ),
            account_record(
                "acct-shared-ab",
                "Family Cash",
                AccountOwnershipType.SHARED,
                household_id=HH_AB,
            ),
            account_record(
                "acct-shared-c",
                "C Family Cash",
                AccountOwnershipType.SHARED,
                household_id=HH_C,
            ),
            account_record(
                "acct-deleted-a",
                "Deleted A",
                AccountOwnershipType.PERSONAL,
                owner_user_id=OWNER_A,
                status=ResourceStatus.DELETED,
            ),
        ]
    )
    yield
    reset_accounts_for_tests()
    reset_transactions_for_tests()


@pytest.fixture
def client_for_actor() -> Iterator[callable[[Actor], TestClient]]:
    clients: list[TestClient] = []

    def factory(current_actor: Actor) -> TestClient:
        app = create_app()
        app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(current_actor)
        client = TestClient(app)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


def account_ids(response_body: dict[str, object]) -> set[str]:
    return {item["id"] for item in response_body["items"]}


def test_list_search_and_autocomplete_return_only_visible_accounts(client_for_actor) -> None:
    client = client_for_actor(ACTOR_A)

    list_response = client.get("/api/v1/accounts")
    assert list_response.status_code == 200
    assert account_ids(list_response.json()) == {"acct-personal-a", "acct-shared-ab"}
    assert "totalCount" not in list_response.text

    search_response = client.get("/api/v1/accounts", params={"q": "wallet"})
    assert account_ids(search_response.json()) == {"acct-personal-a"}

    autocomplete_response = client.get("/api/v1/accounts/autocomplete", params={"q": "cash"})
    assert autocomplete_response.status_code == 200
    assert account_ids(autocomplete_response.json()) == {"acct-shared-ab"}
    assert "currentBalance" not in autocomplete_response.text


def test_active_member_shared_access_excludes_invited_former_and_other_memberships(
    client_for_actor,
) -> None:
    assert account_ids(client_for_actor(ACTOR_B).get("/api/v1/accounts").json()) == {
        "acct-personal-b",
        "acct-shared-ab",
    }
    assert account_ids(client_for_actor(ACTOR_C).get("/api/v1/accounts").json()) == {
        "acct-shared-c"
    }
    assert account_ids(client_for_actor(ACTOR_INVITED).get("/api/v1/accounts").json()) == set()
    assert account_ids(client_for_actor(ACTOR_FORMER).get("/api/v1/accounts").json()) == set()


def test_get_missing_and_inaccessible_accounts_share_neutral_public_shape(client_for_actor) -> None:
    client = client_for_actor(ACTOR_B)

    hidden_response = client.get("/api/v1/accounts/acct-personal-a")
    missing_response = client.get("/api/v1/accounts/acct-missing")

    assert hidden_response.status_code == 404
    assert missing_response.status_code == 404
    assert hidden_response.json()["error"]["code"] == "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
    assert missing_response.json()["error"]["code"] == "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
    assert hidden_response.json()["error"]["message"] == missing_response.json()["error"]["message"]
    assert "A Wallet" not in hidden_response.text


def test_create_derives_personal_owner_and_requires_active_shared_membership(
    client_for_actor,
) -> None:
    client = client_for_actor(ACTOR_A)

    personal_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Derived Owner",
            "accountType": "bank",
            "ownershipType": "personal",
            "currency": "RUB",
            "initialBalance": "12.34",
        },
    )
    assert personal_response.status_code == 201
    personal_data = personal_response.json()["data"]
    assert personal_data["ownerUserId"] == OWNER_A
    assert personal_data["householdId"] is None

    extra_owner_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Foreign Owner Attempt",
            "accountType": "bank",
            "ownershipType": "personal",
            "ownerUserId": OTHER_C,
            "currency": "RUB",
            "initialBalance": "1.00",
        },
    )
    assert extra_owner_response.status_code == 422

    shared_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Shared Allowed",
            "accountType": "cash",
            "ownershipType": "shared",
            "householdId": HH_AB,
            "currency": "RUB",
            "initialBalance": "1.00",
        },
    )
    assert shared_response.status_code == 201
    assert shared_response.json()["data"]["householdId"] == HH_AB
    assert shared_response.json()["data"]["ownerUserId"] is None

    invited_response = client_for_actor(ACTOR_INVITED).post(
        "/api/v1/accounts",
        json={
            "name": "Shared Denied",
            "accountType": "cash",
            "ownershipType": "shared",
            "householdId": HH_AB,
            "currency": "RUB",
            "initialBalance": "1.00",
        },
    )
    assert invited_response.status_code == 404
    assert invited_response.json()["error"]["code"] == "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"


def test_new_financial_account_types_are_accepted_without_weakening_personal_scope(
    client_for_actor,
) -> None:
    client = client_for_actor(ACTOR_A)

    for account_type in ("card", "deposit", "brokerage", "metal", "other"):
        response = client.post(
            "/api/v1/accounts",
            json={
                "name": f"{account_type} account",
                "accountType": account_type,
                "ownershipType": "personal",
                "currency": "RUB",
                "initialBalance": "1.00",
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["accountType"] == account_type
        assert data["ownershipType"] == "personal"
        assert data["ownerUserId"] == OWNER_A
        assert data["householdId"] is None


def test_payment_account_flag_defaults_to_true_and_is_mutable(client_for_actor) -> None:
    client = client_for_actor(ACTOR_A)

    listed = client.get("/api/v1/accounts")
    assert listed.status_code == 200
    assert {item["isPaymentAccount"] for item in listed.json()["items"]} == {True}

    created = client.post(
        "/api/v1/accounts",
        json={
            "name": "Investment Display Only",
            "accountType": "brokerage",
            "ownershipType": "personal",
            "currency": "RUB",
            "initialBalance": "1.00",
            "isPaymentAccount": False,
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["isPaymentAccount"] is False

    updated = client.patch(f"/api/v1/accounts/{data['id']}", json={"isPaymentAccount": True})
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["isPaymentAccount"] is True


def test_update_blocks_ownership_fields_and_foreign_personal_mutation(client_for_actor) -> None:
    owner_client = client_for_actor(ACTOR_A)
    updated = owner_client.patch("/api/v1/accounts/acct-personal-a", json={"name": "Renamed"})
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Renamed"
    assert updated.json()["data"]["ownerUserId"] == OWNER_A

    immutable_response = owner_client.patch(
        "/api/v1/accounts/acct-personal-a",
        json={"ownershipType": "shared", "householdId": HH_AB},
    )
    assert immutable_response.status_code == 422

    foreign_response = client_for_actor(ACTOR_B).patch(
        "/api/v1/accounts/acct-personal-a",
        json={"name": "Nope"},
    )
    assert foreign_response.status_code == 404
    assert "Renamed" not in foreign_response.text


def test_update_snapshot_balance_and_currency_without_transactions_preserves_initial_balance(
    client_for_actor,
) -> None:
    client = client_for_actor(ACTOR_A)

    response = client.patch(
        "/api/v1/accounts/acct-personal-a",
        json={
            "name": "Snapshot Updated",
            "currentBalance": "250.50",
            "currency": "USD",
            "version": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Snapshot Updated"
    assert Decimal(data["currentBalance"]) == Decimal("250.50")
    assert data["currency"] == "USD"
    assert Decimal(data["initialBalance"]) == Decimal("100.00")
    assert data["version"] == 2

    fetched = client.get("/api/v1/accounts/acct-personal-a")
    assert fetched.status_code == 200
    assert Decimal(fetched.json()["data"]["initialBalance"]) == Decimal("100.00")


def test_update_account_stale_version_returns_conflict(client_for_actor) -> None:
    client = client_for_actor(ACTOR_A)
    first = client.patch("/api/v1/accounts/acct-personal-a", json={"name": "Fresh", "version": 1})
    assert first.status_code == 200

    stale = client.patch(
        "/api/v1/accounts/acct-personal-a",
        json={"name": "Stale", "version": 1},
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICTING_UPDATE"
    assert stale.json()["error"]["message"] == "Conflicting update."


def test_update_account_currency_with_transactions_returns_conflict(client_for_actor) -> None:
    reset_transactions_for_tests(
        [
            transaction_record(
                "txn-account-currency-lock",
                account_id="acct-personal-a",
            )
        ]
    )
    client = client_for_actor(ACTOR_A)

    response = client.patch(
        "/api/v1/accounts/acct-personal-a",
        json={"currency": "USD", "version": 1},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ACCOUNT_CURRENCY_IMMUTABLE_AFTER_TRANSACTIONS"
    assert (
        response.json()["error"]["message"]
        == "Account currency cannot be changed after transactions exist."
    )


def test_archive_restore_and_delete_preserve_visibility_boundary(client_for_actor) -> None:
    member_client = client_for_actor(ACTOR_B)

    archived = member_client.post("/api/v1/accounts/acct-shared-ab/archive")
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    blocked_update = member_client.patch(
        "/api/v1/accounts/acct-shared-ab",
        json={"name": "Blocked"},
    )
    assert blocked_update.status_code == 409
    assert blocked_update.json()["error"]["code"] == "ARCHIVED_RECORD_NOT_MUTABLE"

    restored = client_for_actor(ACTOR_A).post("/api/v1/accounts/acct-shared-ab/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "active"

    deleted = member_client.delete("/api/v1/accounts/acct-shared-ab")
    assert deleted.status_code == 204
    assert deleted.content == b""

    hidden_after_delete = client_for_actor(ACTOR_A).get("/api/v1/accounts/acct-shared-ab")
    assert hidden_after_delete.status_code == 404
