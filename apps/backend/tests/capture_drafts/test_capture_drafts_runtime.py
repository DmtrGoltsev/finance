from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.accounts.repository import AccountRecord, InMemoryAccountRepository
from app.authz import AccountOwnershipType, Actor, ResourceStatus
from app.capture_drafts.repository import InMemoryCaptureDraftRepository
from app.capture_drafts.schemas import CaptureDraftCreateRequest
from app.capture_drafts.service import CaptureDraftService
from app.categories.repository import CategoryRecord, InMemoryCategoryRepository
from app.categories.schemas import CategoryScope, CategoryType, RecordStatus
from app.transactions.repository import InMemoryTransactionRepository, TransactionFilters
from app.transactions.service import TransactionService
from tests.transactions.test_transactions_db_runtime import (
    _assert_same_public_error,
    _client_for_actor,
)

pytest_plugins = ["tests.transactions.test_transactions_db_runtime"]


def _draft_payload(transaction_graph: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
    return {
        "idempotencyKey": idempotency_key,
        "captureSource": "sms",
        "capturedAt": "2026-05-17T14:01:00+00:00",
        "occurredAt": "2026-05-17T14:00:00+00:00",
        "amount": "12.3400",
        "currency": "RUB",
        "description": "sanitized grocery candidate",
        "merchantName": "Safe Market",
        "accountId": transaction_graph["accounts"]["acc_a_cash"],
        "categoryId": transaction_graph["categories"]["cat_a_food"],
        "confidence": "0.8700",
        "sourceAppPackage": "ru.bank.safe",
        "sourceAppLabel": "Bank",
        "evidenceHash": "sha256:capture-fixture",
    }


def test_capture_draft_create_list_dedup_update_and_confirm(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = _draft_payload(transaction_graph, idempotency_key="capture-1")

    with _client_for_actor(owner) as client:
        created = client.post("/api/v1/capture-drafts", json=payload)
        duplicate = client.post(
            "/api/v1/capture-drafts",
            json={**payload, "description": "must not create a second draft"},
        )
        listed = client.get("/api/v1/capture-drafts", params={"status": "pending"})

        draft_id = created.json()["data"]["id"]
        updated = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={
                "amount": "13.0000",
                "description": "reviewed grocery candidate",
                "merchantName": "Reviewed Market",
            },
        )
        confirmed = client.post(f"/api/v1/capture-drafts/{draft_id}/confirm")
        transaction_id = confirmed.json()["data"]["transactionId"]
        transaction = client.get(f"/api/v1/transactions/{transaction_id}")
        confirm_again = client.post(f"/api/v1/capture-drafts/{draft_id}/confirm")
        transactions_after_replay = client.get(
            "/api/v1/transactions",
            params={"q": "reviewed grocery candidate"},
        )

    assert created.status_code == 201, created.text
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["data"]["id"] == draft_id
    assert duplicate.json()["data"]["description"] == "sanitized grocery candidate"
    assert [item["id"] for item in listed.json()["items"]] == [draft_id]

    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["amount"] == "13.0000"
    assert updated.json()["data"]["merchantName"] == "Reviewed Market"

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "confirmed"
    assert confirmed.json()["data"]["transactionId"]
    assert transaction.status_code == 200
    assert transaction.json()["data"]["sourceType"] == "manual"
    assert transaction.json()["data"]["transactionType"] == "expense"
    assert transaction.json()["data"]["description"] == "reviewed grocery candidate"
    assert transaction.json()["data"]["amount"] == "13.0000"
    assert confirm_again.status_code == 200
    assert confirm_again.json()["data"]["status"] == "confirmed"
    assert confirm_again.json()["data"]["transactionId"] == transaction_id
    assert transactions_after_replay.status_code == 200
    assert [
        item["id"]
        for item in transactions_after_replay.json()["items"]
        if item["description"] == "reviewed grocery candidate"
    ] == [transaction_id]


def test_in_memory_capture_draft_repeated_confirm_is_idempotent() -> None:
    now = datetime(2026, 5, 17, 14, 0, tzinfo=UTC)
    owner_id = "owner_a"
    account_id = "acct_a_cash"
    category_id = "cat_a_food"
    actor = Actor(user_id=owner_id, request_id="req-owner")

    accounts = InMemoryAccountRepository()
    accounts.seed(
        [
            AccountRecord(
                id=account_id,
                name="Cash",
                account_type="cash",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id=owner_id,
                household_id=None,
                currency="RUB",
                initial_balance=Decimal("100.0000"),
                current_balance=Decimal("100.0000"),
                created_by_user_id=owner_id,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            )
        ]
    )
    categories = InMemoryCategoryRepository()
    categories.reset(
        [
            CategoryRecord(
                id=category_id,
                name="Food",
                type=CategoryType.EXPENSE,
                scope=CategoryScope.PERSONAL,
                owner_user_id=owner_id,
                household_id=None,
                icon_key="food",
                color="#336699",
                status=RecordStatus.ACTIVE,
                created_by_user_id=owner_id,
                created_at=now,
                updated_at=now,
                archived_at=None,
                deleted_at=None,
                version=1,
            )
        ]
    )
    transactions = InMemoryTransactionRepository()
    service = CaptureDraftService(
        InMemoryCaptureDraftRepository(),
        TransactionService(transactions, accounts, categories),
    )

    draft = service.create_draft(
        actor=actor,
        request=CaptureDraftCreateRequest(
            idempotency_key="memory-replay",
            capture_source="sms",
            captured_at=now,
            occurred_at=now,
            amount=Decimal("12.3400"),
            currency="RUB",
            description="memory reviewed grocery candidate",
            account_id=account_id,
            category_id=category_id,
        ),
    )
    confirmed = service.confirm_draft(actor=actor, draft_id=draft.id)
    confirmed_again = service.confirm_draft(actor=actor, draft_id=draft.id)

    created_transactions = transactions.list_by_visible_accounts(
        [account_id],
        filters=TransactionFilters(q="memory reviewed grocery candidate"),
    )

    assert confirmed.status == "confirmed"
    assert confirmed.transaction_id is not None
    assert confirmed_again.status == "confirmed"
    assert confirmed_again.transaction_id == confirmed.transaction_id
    assert [record.id for record in created_transactions] == [confirmed.transaction_id]


def test_capture_draft_discard_and_access_isolation(transaction_graph: dict[str, Any]) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    member = transaction_graph["actors"]["member_b"]
    payload = _draft_payload(transaction_graph, idempotency_key="capture-discard")

    with _client_for_actor(owner) as client:
        created = client.post("/api/v1/capture-drafts", json=payload)
        draft_id = created.json()["data"]["id"]

    with _client_for_actor(member) as client:
        listed = client.get("/api/v1/capture-drafts")
        inaccessible = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"description": "member cannot edit owner draft"},
        )
        missing = client.patch(
            f"/api/v1/capture-drafts/{uuid4()}",
            json={"description": "missing draft"},
        )

    with _client_for_actor(owner) as client:
        discarded = client.post(f"/api/v1/capture-drafts/{draft_id}/discard")
        confirm_discarded = client.post(f"/api/v1/capture-drafts/{draft_id}/confirm")
        update_discarded = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"description": "cannot update after discard"},
        )

    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert inaccessible.status_code == missing.status_code == 404
    _assert_same_public_error(inaccessible, missing)
    assert draft_id not in inaccessible.text
    assert discarded.status_code == 200
    assert discarded.json()["data"]["status"] == "discarded"
    assert confirm_discarded.status_code == 409
    assert update_discarded.status_code == 409


def test_capture_drafts_reject_raw_text_fields(transaction_graph: dict[str, Any]) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = {
        **_draft_payload(transaction_graph, idempotency_key="capture-raw"),
        "rawMessage": "secret sms body must never be stored",
        "body": "secret body",
        "text": "secret text",
    }

    with _client_for_actor(owner) as client:
        rejected = client.post("/api/v1/capture-drafts", json=payload)
        listed = client.get("/api/v1/capture-drafts")

    assert rejected.status_code == 422
    assert "secret sms body" not in rejected.text
    assert "secret body" not in rejected.text
    assert "secret text" not in rejected.text
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_capture_draft_create_rejects_inaccessible_missing_and_invalid_refs_neutrally(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = _draft_payload(transaction_graph, idempotency_key="capture-ref-create")
    inaccessible_account_id = transaction_graph["accounts"]["acc_b_cash"]
    inaccessible_category_id = transaction_graph["categories"]["cat_b_food"]

    with _client_for_actor(owner) as client:
        inaccessible_account = client.post(
            "/api/v1/capture-drafts",
            json={**payload, "accountId": inaccessible_account_id},
        )
        missing_account = client.post(
            "/api/v1/capture-drafts",
            json={
                **payload,
                "idempotencyKey": "capture-ref-create-missing-account",
                "accountId": str(uuid4()),
            },
        )
        invalid_account = client.post(
            "/api/v1/capture-drafts",
            json={
                **payload,
                "idempotencyKey": "capture-ref-create-invalid-account",
                "accountId": "acct-not-a-uuid",
            },
        )
        inaccessible_category = client.post(
            "/api/v1/capture-drafts",
            json={
                **payload,
                "idempotencyKey": "capture-ref-create-inaccessible-category",
                "categoryId": inaccessible_category_id,
            },
        )
        missing_category = client.post(
            "/api/v1/capture-drafts",
            json={
                **payload,
                "idempotencyKey": "capture-ref-create-missing-category",
                "categoryId": str(uuid4()),
            },
        )
        invalid_category = client.post(
            "/api/v1/capture-drafts",
            json={
                **payload,
                "idempotencyKey": "capture-ref-create-invalid-category",
                "categoryId": "cat-not-a-uuid",
            },
        )
        listed = client.get("/api/v1/capture-drafts")

    assert inaccessible_account.status_code == missing_account.status_code == 404
    _assert_same_public_error(inaccessible_account, missing_account)
    _assert_same_public_error(inaccessible_account, invalid_account)
    assert invalid_account.status_code != 500
    assert inaccessible_account_id not in inaccessible_account.text

    assert inaccessible_category.status_code == missing_category.status_code == 404
    _assert_same_public_error(inaccessible_category, missing_category)
    _assert_same_public_error(inaccessible_category, invalid_category)
    assert invalid_category.status_code != 500
    assert inaccessible_category_id not in inaccessible_category.text

    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_capture_draft_update_rejects_inaccessible_missing_and_invalid_refs_neutrally(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = _draft_payload(transaction_graph, idempotency_key="capture-ref-update")
    inaccessible_account_id = transaction_graph["accounts"]["acc_b_cash"]
    inaccessible_category_id = transaction_graph["categories"]["cat_b_food"]

    with _client_for_actor(owner) as client:
        created = client.post("/api/v1/capture-drafts", json=payload)
        draft_id = created.json()["data"]["id"]

        inaccessible_account = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"accountId": inaccessible_account_id},
        )
        missing_account = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"accountId": str(uuid4())},
        )
        invalid_account = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"accountId": "acct-not-a-uuid"},
        )
        inaccessible_category = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"categoryId": inaccessible_category_id},
        )
        missing_category = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"categoryId": str(uuid4())},
        )
        invalid_category = client.patch(
            f"/api/v1/capture-drafts/{draft_id}",
            json={"categoryId": "cat-not-a-uuid"},
        )
        listed = client.get("/api/v1/capture-drafts")

    assert created.status_code == 201, created.text
    assert inaccessible_account.status_code == missing_account.status_code == 404
    _assert_same_public_error(inaccessible_account, missing_account)
    _assert_same_public_error(inaccessible_account, invalid_account)
    assert invalid_account.status_code != 500
    assert inaccessible_account_id not in inaccessible_account.text

    assert inaccessible_category.status_code == missing_category.status_code == 404
    _assert_same_public_error(inaccessible_category, missing_category)
    _assert_same_public_error(inaccessible_category, invalid_category)
    assert invalid_category.status_code != 500
    assert inaccessible_category_id not in inaccessible_category.text

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    stored = listed.json()["items"][0]
    assert stored["accountId"] == payload["accountId"]
    assert stored["categoryId"] == payload["categoryId"]
