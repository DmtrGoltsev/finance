from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.authz import Actor
from app.config import get_settings
from app.db.models import SyncChange
from app.db.session import sync_session_scope
from tests.transactions.test_transactions_db_runtime import (
    _assert_no_hidden_markers,
    _assert_same_public_error,
    _client_for_actor,
)
from tests.transactions.test_transactions_db_runtime import (
    transaction_graph as _transaction_graph_fixture,
)

transaction_graph = _transaction_graph_fixture

def _transfer_payload(
    graph: dict[str, Any],
    *,
    source: str,
    counterparty: str,
    amount: str = "1.2500",
    currency: str = "RUB",
) -> dict[str, Any]:
    return {
        "transactionType": "transfer",
        "accountId": graph["accounts"][source],
        "counterpartyAccountId": graph["accounts"].get(counterparty, counterparty),
        "amount": amount,
        "currency": currency,
        "occurredAt": "2026-05-17T14:00:00+00:00",
        "description": "transfer safety fixture",
        "sourceType": "manual",
    }


def _balance(client: Any, account_id: str) -> Decimal:
    response = client.get(f"/api/v1/accounts/{account_id}")
    assert response.status_code == 200
    return Decimal(response.json()["data"]["currentBalance"])


def _sync_changes_for(entity_ids: set[str]) -> list[SyncChange]:
    with sync_session_scope(get_settings()) as session:
        return list(
            session.execute(
                select(SyncChange)
                .where(SyncChange.entity_id.in_([UUID(entity_id) for entity_id in entity_ids]))
                .order_by(SyncChange.seq.asc())
            ).scalars()
        )


def _visible_transfer_ids(client: Any) -> set[str]:
    response = client.get("/api/v1/transactions", params={"transactionType": "transfer"})
    assert response.status_code == 200
    return {item["id"] for item in response.json()["items"]}


def _assert_transfer_error_has_no_hidden_details(response: Any, *hidden_ids: str) -> None:
    assert set(response.json()) == {"error"}
    assert "details" not in response.json()["error"]
    _assert_no_hidden_markers(response.text)
    for hidden_id in hidden_ids:
        assert hidden_id not in response.text
    assert "transfer safety fixture" not in response.text
    assert "1.2500" not in response.text


def test_same_scope_transfers_are_created_and_adjust_balances(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    member = transaction_graph["actors"]["member_b"]
    owner_cash = transaction_graph["accounts"]["acc_a_cash"]
    owner_savings = transaction_graph["accounts"]["acc_a_savings"]
    shared_cash = transaction_graph["accounts"]["acc_ab_cash"]
    shared_savings = transaction_graph["accounts"]["acc_ab_savings"]

    with _client_for_actor(owner) as client:
        personal = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_a_savings",
            ),
        )
        assert personal.status_code == 201
        personal_body = personal.json()["data"]
        personal_detail = client.get(f"/api/v1/transactions/{personal_body['id']}")

        assert personal_body["transactionType"] == "transfer"
        assert personal_body["transferScope"] == "personal_same_owner"
        assert personal_body["transferStatus"] == "posted"
        assert personal_body["categoryId"] is None
        assert personal_body["counterpartyAccountId"] == owner_savings
        assert personal_detail.status_code == 200
        assert _balance(client, owner_cash) == Decimal("98.7500")
        assert _balance(client, owner_savings) == Decimal("101.2500")

    with _client_for_actor(member) as client:
        shared = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_ab_cash",
                counterparty="acc_ab_savings",
                amount="2.0000",
            ),
        )
        assert shared.status_code == 201
        shared_body = shared.json()["data"]
        shared_detail = client.get(f"/api/v1/transactions/{shared_body['id']}")

        assert shared_body["transferScope"] == "household_same_household"
        assert shared_body["counterpartyAccountId"] == shared_savings
        assert shared_detail.status_code == 200
        assert _balance(client, shared_cash) == Decimal("98.0000")
        assert _balance(client, shared_savings) == Decimal("102.0000")


def test_rest_transfer_create_emits_account_sync_changes_with_updated_balances(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    owner_cash = transaction_graph["accounts"]["acc_a_cash"]
    owner_savings = transaction_graph["accounts"]["acc_a_savings"]

    with _client_for_actor(owner) as client:
        created = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_a_savings",
                amount="7.5000",
            ),
        )

    assert created.status_code == 201, created.text
    transaction_id = created.json()["data"]["id"]
    changes = _sync_changes_for({transaction_id, owner_cash, owner_savings})
    assert [change.entity_type for change in changes] == [
        "transactions",
        "accounts",
        "accounts",
    ]
    account_payloads = {
        str(change.entity_id): change.payload
        for change in changes
        if change.entity_type == "accounts"
    }
    assert account_payloads[owner_cash]["currentBalance"] == "92.5000"
    assert account_payloads[owner_savings]["currentBalance"] == "107.5000"
    assert all(change.change_type == "update" for change in changes[1:])


def test_transfer_denials_are_neutral_and_leave_no_visible_partial_rows(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    invited = transaction_graph["actors"]["invited_ab"]
    owner_cash = transaction_graph["accounts"]["acc_a_cash"]
    owner_savings = transaction_graph["accounts"]["acc_a_savings"]
    member_cash = transaction_graph["accounts"]["acc_b_cash"]
    foreign_shared = transaction_graph["accounts"]["acc_c_shared"]
    shared_cash = transaction_graph["accounts"]["acc_ab_cash"]
    shared_savings = transaction_graph["accounts"]["acc_ab_savings"]

    with _client_for_actor(owner) as client:
        before_ids = _visible_transfer_ids(client)
        before_cash = _balance(client, owner_cash)
        before_savings = _balance(client, owner_savings)

        personal_to_shared = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_ab_cash",
            ),
        )
        shared_to_personal = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_ab_cash",
                counterparty="acc_a_cash",
            ),
        )
        cross_user = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_b_cash",
            ),
        )
        cross_household = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_ab_cash",
                counterparty="acc_c_shared",
            ),
        )
        cross_currency = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_a_usd",
                currency="RUB",
            ),
        )
        missing = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty=str(uuid4()),
            ),
        )

        assert personal_to_shared.status_code == shared_to_personal.status_code == 422
        assert personal_to_shared.json()["error"]["code"] == "TRANSFER_SCOPE_NOT_SUPPORTED"
        _assert_same_public_error(personal_to_shared, shared_to_personal)
        assert cross_user.status_code == cross_household.status_code == missing.status_code == 404
        assert cross_user.json()["error"]["code"] == (
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
        )
        assert cross_currency.status_code == 400
        assert cross_currency.json()["error"]["code"] == "INVALID_CURRENCY"
        _assert_transfer_error_has_no_hidden_details(cross_user, member_cash)
        _assert_transfer_error_has_no_hidden_details(cross_household, foreign_shared)
        _assert_transfer_error_has_no_hidden_details(missing)
        assert _visible_transfer_ids(client) == before_ids
        assert _balance(client, owner_cash) == before_cash
        assert _balance(client, owner_savings) == before_savings

    with _client_for_actor(invited) as client:
        denied_shared = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_ab_cash",
                counterparty="acc_ab_savings",
            ),
        )

        assert denied_shared.status_code == 404
        assert denied_shared.json()["error"]["code"] == (
            "REFERENCED_RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
        )
        _assert_transfer_error_has_no_hidden_details(denied_shared, shared_cash, shared_savings)


def test_transfer_update_delete_restore_are_versioned_and_atomic(
    transaction_graph: dict[str, Any],
) -> None:
    owner: Actor = transaction_graph["actors"]["owner_a"]
    source = transaction_graph["accounts"]["acc_a_cash"]
    counterparty = transaction_graph["accounts"]["acc_a_savings"]

    with _client_for_actor(owner) as client:
        created = client.post(
            "/api/v1/transactions",
            json=_transfer_payload(
                transaction_graph,
                source="acc_a_cash",
                counterparty="acc_a_savings",
                amount="1.0000",
            ),
        )
        assert created.status_code == 201
        transaction = created.json()["data"]
        transaction_id = transaction["id"]

        updated = client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={
                "amount": "2.0000",
                "description": "updated transfer safety fixture",
                "version": transaction["version"],
            },
        )
        stale = client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"amount": "3.0000", "version": transaction["version"]},
        )

        assert updated.status_code == 200
        assert updated.json()["data"]["amount"] == "2.0000"
        assert stale.status_code == 409
        assert _balance(client, source) == Decimal("98.0000")
        assert _balance(client, counterparty) == Decimal("102.0000")

        deleted = client.delete(f"/api/v1/transactions/{transaction_id}")
        after_delete = client.get(f"/api/v1/transactions/{transaction_id}")
        assert deleted.status_code == 204
        assert after_delete.status_code == 404
        assert _balance(client, source) == Decimal("100.0000")
        assert _balance(client, counterparty) == Decimal("100.0000")

        restored = client.post(f"/api/v1/transactions/{transaction_id}/restore")
        after_restore = client.get(f"/api/v1/transactions/{transaction_id}")
        assert restored.status_code == 200
        assert after_restore.status_code == 200
        assert restored.json()["data"]["transferScope"] == "personal_same_owner"
        assert _balance(client, source) == Decimal("98.0000")
        assert _balance(client, counterparty) == Decimal("102.0000")
