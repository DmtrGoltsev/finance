from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import Actor, Membership, MembershipStatus
from app.db.base import Base
from app.db.models import Account, Category, Household, Transaction, User
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = (
    REPO_ROOT
    / "qa"
    / "fixtures"
    / "owner-member-other-invited-former-v1"
    / "canonical-uuid-graph.json"
)
BASE_TIME = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    Account.__table__,
    Category.__table__,
    Transaction.__table__,
]


@pytest.fixture
def transaction_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'transactions.sqlite').as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE", "db")

    from app.config import get_settings

    get_settings.cache_clear()
    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=TABLES)
    graph = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    labels = _seed_fixture_graph(engine, graph)

    try:
        yield labels
    finally:
        engine.dispose()
        get_settings.cache_clear()
        sync_engine_for_url.cache_clear()


def _app_for_actor(actor: Actor) -> FastAPI:
    app = create_app()
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    return app


@contextmanager
def _client_for_actor(actor: Actor) -> Iterator[TestClient]:
    with TestClient(_app_for_actor(actor)) as client:
        yield client


def _seed_fixture_graph(engine: Any, graph: dict[str, Any]) -> dict[str, Any]:
    actors = {item["label"]: item for item in graph["actors"]}
    households = {item["label"]: item for item in graph["households"]}
    accounts = {item["label"]: item for item in graph["accounts"]}
    categories = {item["label"]: item for item in graph["categories"] if item["scope"] != "virtual"}
    transactions = {item["label"]: item for item in graph["plannedTransactions"]}

    labels: dict[str, Any] = {
        "actors": {},
        "households": {label: item["canonicalId"] for label, item in households.items()},
        "accounts": {label: item["canonicalId"] for label, item in accounts.items()},
        "categories": {label: item["canonicalId"] for label, item in categories.items()},
        "transactions": {label: item["canonicalId"] for label, item in transactions.items()},
        "planned_transactions": graph["plannedTransactions"],
    }

    actor_memberships: dict[str, list[Membership]] = {label: [] for label in actors}
    for membership in graph["memberships"]:
        actor = membership["actor"]
        household_id = households[membership["household"]]["canonicalId"]
        actor_id = actors[actor]["canonicalId"]
        actor_memberships[actor].append(
            Membership(
                user_id=actor_id,
                household_id=household_id,
                status=MembershipStatus(membership["status"]),
            )
        )

    for label, actor in actors.items():
        labels["actors"][label] = Actor(
            user_id=actor["canonicalId"],
            request_id=f"req-{label}",
            memberships=tuple(actor_memberships[label]),
        )

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        for label, actor in actors.items():
            session.add(
                User(
                    id=UUID(actor["canonicalId"]),
                    email_normalized=f"{label}@example.test",
                    password_hash="hash-placeholder",
                    display_name=label,
                    auth_status="active",
                    record_status="active",
                    session_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for label, household in households.items():
            creator = actors[household["activeActors"][0]]["canonicalId"]
            session.add(
                Household(
                    id=UUID(household["canonicalId"]),
                    name=label,
                    created_by_user_id=UUID(creator),
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for membership in graph["memberships"]:
            status = membership["status"]
            session.add(
                DbMembership(
                    id=UUID(membership["canonicalId"]),
                    household_id=UUID(households[membership["household"]]["canonicalId"]),
                    user_id=UUID(actors[membership["actor"]]["canonicalId"]),
                    membership_status=status,
                    invited_at=BASE_TIME if status == "invited" else None,
                    joined_at=BASE_TIME if status == "active" else None,
                    ended_at=BASE_TIME if status in {"left", "revoked"} else None,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for label, account in accounts.items():
            owner = actors[account["ownerActor"]]["canonicalId"] if account["ownerActor"] else None
            household = households[account["household"]]["canonicalId"] if account["household"] else None
            session.add(
                Account(
                    id=UUID(account["canonicalId"]),
                    name=label,
                    account_type="cash",
                    ownership_type="personal" if account["scope"] == "personal" else "shared",
                    owner_user_id=UUID(owner) if owner else None,
                    household_id=UUID(household) if household else None,
                    currency=account["currency"],
                    initial_balance_amount=Decimal("100.0000"),
                    current_balance_amount=Decimal("100.0000"),
                    record_status="active",
                    created_by_user_id=UUID(owner or actors["owner_a"]["canonicalId"]),
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for label, category in categories.items():
            owner = actors[category["ownerActor"]]["canonicalId"] if category["ownerActor"] else None
            household = households[category["household"]]["canonicalId"] if category["household"] else None
            session.add(
                Category(
                    id=UUID(category["canonicalId"]),
                    name=label,
                    category_type=category["categoryType"],
                    category_scope=category["scope"],
                    owner_user_id=UUID(owner) if owner else None,
                    household_id=UUID(household) if household else None,
                    icon_key="tag",
                    color="#336699",
                    record_status="active",
                    created_by_user_id=UUID(owner or actors["owner_a"]["canonicalId"]),
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for offset, (label, transaction) in enumerate(transactions.items(), start=1):
            account = accounts[transaction["account"]]
            category = categories[transaction["category"]]
            actor_label = transaction["allowedActors"][0]
            session.add(
                Transaction(
                    id=UUID(transaction["canonicalId"]),
                    transaction_type=transaction["transactionType"],
                    account_id=UUID(account["canonicalId"]),
                    counterparty_account_id=None,
                    category_id=UUID(category["canonicalId"]),
                    amount=Decimal("10.0000") + Decimal(offset),
                    currency=account["currency"],
                    occurred_at=BASE_TIME + timedelta(minutes=offset),
                    description=f"{label} fixture",
                    source_type="manual",
                    transfer_scope=None,
                    transfer_status=None,
                    record_status=transaction["recordStatus"],
                    created_by_user_id=UUID(actors[actor_label]["canonicalId"]),
                    last_edited_by_user_id=UUID(actors[actor_label]["canonicalId"]),
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        session.flush()
    return labels


def _ids(body: dict[str, Any]) -> set[str]:
    return {str(item["id"]) for item in body["items"]}


def _assert_no_hidden_markers(body_text: str) -> None:
    lowered = body_text.lower()
    for marker in ("totalcount", "hiddencount", "filteredout", "hidden count", "hidden_count"):
        assert marker not in lowered


def _assert_same_public_error(first: Any, second: Any) -> None:
    assert first.status_code == second.status_code
    first_body = first.json()
    second_body = second.json()
    first_body["error"]["requestId"] = "<request-id>"
    second_body["error"]["requestId"] = "<request-id>"
    assert first_body == second_body
    _assert_no_hidden_markers(first.text)
    _assert_no_hidden_markers(second.text)


def test_db_backed_transactions_visibility_matrix(transaction_graph: dict[str, Any]) -> None:
    planned = transaction_graph["planned_transactions"]

    for actor_label, actor in transaction_graph["actors"].items():
        expected = {
            transaction_graph["transactions"][item["label"]]
            for item in planned
            if actor_label in item["allowedActors"]
        }
        with _client_for_actor(actor) as client:
            response = client.get("/api/v1/transactions")
            autocomplete = client.get("/api/v1/transactions/autocomplete")

        assert response.status_code == 200
        assert autocomplete.status_code == 200
        assert _ids(response.json()) == expected
        assert _ids(autocomplete.json()).issubset(expected)
        _assert_no_hidden_markers(response.text)


def test_db_backed_transaction_detail_missing_and_inaccessible_are_neutral(
    transaction_graph: dict[str, Any],
) -> None:
    owner_personal_txn = transaction_graph["transactions"]["txn_a_income_may"]
    member = transaction_graph["actors"]["member_b"]

    with _client_for_actor(member) as client:
        inaccessible = client.get(f"/api/v1/transactions/{owner_personal_txn}")
        missing = client.get(f"/api/v1/transactions/{uuid4()}")

    assert inaccessible.status_code == missing.status_code == 404
    _assert_same_public_error(inaccessible, missing)
    assert owner_personal_txn not in inaccessible.text


def test_db_backed_transaction_create_update_delete_restore(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    account_id = transaction_graph["accounts"]["acc_a_cash"]
    category_id = transaction_graph["categories"]["cat_a_food"]

    with _client_for_actor(owner) as client:
        created = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "12.3400",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:00:00+00:00",
                "description": "manual db lifecycle",
                "sourceType": "manual",
            },
        )
        assert created.status_code == 201
        transaction_id = created.json()["data"]["id"]

        updated = client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={
                "amount": "13.0000",
                "description": "manual db lifecycle updated",
                "version": created.json()["data"]["version"],
            },
        )
        stale = client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"amount": "14.0000", "version": created.json()["data"]["version"]},
        )
        deleted = client.delete(f"/api/v1/transactions/{transaction_id}")
        after_delete = client.get(f"/api/v1/transactions/{transaction_id}")
        restored = client.post(f"/api/v1/transactions/{transaction_id}/restore")
        after_restore = client.get(f"/api/v1/transactions/{transaction_id}")

    assert updated.status_code == 200
    assert updated.json()["data"]["amount"] == "13.0000"
    assert stale.status_code == 409
    assert deleted.status_code == 204
    assert after_delete.status_code == 404
    assert restored.status_code == 200
    assert after_restore.status_code == 200
    assert after_restore.json()["data"]["description"] == "manual db lifecycle updated"


def test_transaction_referenced_ids_and_shared_membership_are_enforced(
    transaction_graph: dict[str, Any],
) -> None:
    owner_account_id = transaction_graph["accounts"]["acc_a_cash"]
    shared_account_id = transaction_graph["accounts"]["acc_ab_cash"]
    member_category_id = transaction_graph["categories"]["cat_b_food"]
    shared_category_id = transaction_graph["categories"]["cat_ab_groceries"]
    member = transaction_graph["actors"]["member_b"]
    invited = transaction_graph["actors"]["invited_ab"]

    member_payload = {
        "transactionType": "expense",
        "accountId": owner_account_id,
        "categoryId": member_category_id,
        "amount": "1.0000",
        "currency": "RUB",
        "occurredAt": "2026-05-17T14:00:00+00:00",
        "sourceType": "manual",
    }
    missing_payload = {**member_payload, "accountId": str(uuid4())}

    with _client_for_actor(member) as client:
        inaccessible_account = client.post("/api/v1/transactions", json=member_payload)
        missing_account = client.post("/api/v1/transactions", json=missing_payload)

    with _client_for_actor(invited) as client:
        denied_shared = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": shared_account_id,
                "categoryId": shared_category_id,
                "amount": "1.0000",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:00:00+00:00",
                "sourceType": "manual",
            },
        )

    assert inaccessible_account.status_code == missing_account.status_code == 404
    _assert_same_public_error(inaccessible_account, missing_account)
    assert owner_account_id not in inaccessible_account.text
    assert denied_shared.status_code == 404
    assert shared_account_id not in denied_shared.text


def test_transfer_writes_are_available_for_same_scope_runtime_worker(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    with _client_for_actor(owner) as client:
        response = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "transfer",
                "accountId": transaction_graph["accounts"]["acc_a_cash"],
                "counterpartyAccountId": transaction_graph["accounts"]["acc_a_savings"],
                "amount": "1.0000",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:00:00+00:00",
                "sourceType": "manual",
            },
        )

    assert response.status_code == 201
    assert response.json()["data"]["transactionType"] == "transfer"
    assert response.json()["data"]["transferScope"] == "personal_same_owner"
