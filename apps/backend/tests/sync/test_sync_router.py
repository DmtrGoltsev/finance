from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import Actor
from app.db.base import Base
from app.db.models import (
    Account,
    AccountBalanceSnapshot,
    AssetCategory,
    Category,
    Household,
    PlanningAllocation,
    PlanningIncomeSource,
    PlanningPlan,
    SyncChange,
    SyncClient,
    SyncClientMutation,
    Transaction,
    User,
)
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url
from app.main import create_app

BASE_TIME = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
SLICE_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    AssetCategory.__table__,
    Account.__table__,
    AccountBalanceSnapshot.__table__,
    Category.__table__,
    Transaction.__table__,
    PlanningPlan.__table__,
    PlanningIncomeSource.__table__,
    PlanningAllocation.__table__,
    SyncClient.__table__,
    SyncChange.__table__,
    SyncClientMutation.__table__,
]


@pytest.fixture
def sync_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'sync.sqlite').as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE", "db")

    from app.config import get_settings

    get_settings.cache_clear()
    sync_engine_for_url.cache_clear()
    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=SLICE_TABLES)

    owner_id = uuid4()
    other_id = uuid4()
    account_id = uuid4()
    category_id = uuid4()
    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add_all(
            [
                _user(owner_id, "owner"),
                _user(other_id, "other"),
                Account(
                    id=account_id,
                    name="Owner Cash",
                    account_type="cash",
                    ownership_type="personal",
                    owner_user_id=owner_id,
                    household_id=None,
                    currency="RUB",
                    initial_balance_amount=Decimal("100.0000"),
                    current_balance_amount=Decimal("100.0000"),
                    record_status="active",
                    created_by_user_id=owner_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                AccountBalanceSnapshot(
                    id=uuid4(),
                    account_id=account_id,
                    snapshot_date=BASE_TIME.date(),
                    balance_amount=Decimal("100.0000"),
                    currency="RUB",
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                Category(
                    id=category_id,
                    name="Food",
                    category_type="expense",
                    category_scope="personal",
                    owner_user_id=owner_id,
                    household_id=None,
                    icon_key="tag",
                    color="#336699",
                    record_status="active",
                    created_by_user_id=owner_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
            ]
        )
        session.flush()

    try:
        yield {
            "engine": engine,
            "owner": Actor(user_id=str(owner_id), request_id="req-owner"),
            "other": Actor(user_id=str(other_id), request_id="req-other"),
            "account_id": str(account_id),
            "category_id": str(category_id),
        }
    finally:
        engine.dispose()
        get_settings.cache_clear()
        sync_engine_for_url.cache_clear()


def _app_for_actor(actor: Actor) -> FastAPI:
    app = create_app()
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    return app


def _client_for_actor(actor: Actor) -> TestClient:
    return TestClient(_app_for_actor(actor))


def _user(user_id: UUID, label: str) -> User:
    return User(
        id=user_id,
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


def _create_push_body(
    *,
    entity_id: UUID,
    client_mutation_id: str = "mutation-create-1",
    amount: str = "12.3400",
) -> dict[str, Any]:
    return {
        "deviceId": "android-test-device",
        "clientSchemaVersion": 1,
        "mutations": [
            {
                "clientMutationId": client_mutation_id,
                "entityType": "transactions",
                "entityId": str(entity_id),
                "operation": "create",
                "payload": {
                    "transactionType": "expense",
                    "accountId": "<filled-by-test>",
                    "categoryId": "<filled-by-test>",
                    "amount": amount,
                    "currency": "RUB",
                    "transactionDate": "2026-06-14",
                    "sourceType": "manual",
                },
            }
        ],
    }


def _push_body(sync_graph: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    body = _create_push_body(**kwargs)
    body["mutations"][0]["payload"]["accountId"] = sync_graph["account_id"]
    body["mutations"][0]["payload"]["categoryId"] = sync_graph["category_id"]
    return body


def _transaction_count(sync_graph: dict[str, Any], transaction_id: UUID) -> int:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.id == transaction_id)
            )
            or 0
        )


def _entity_count(sync_graph: dict[str, Any], model: type, entity_id: UUID) -> int:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        return int(
            session.scalar(select(func.count()).select_from(model).where(model.id == entity_id))
            or 0
        )


def _sync_change_count(sync_graph: dict[str, Any], transaction_id: UUID) -> int:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SyncChange)
                .where(SyncChange.entity_id == transaction_id)
            )
            or 0
        )


def _sync_client_mutation_count(sync_graph: dict[str, Any]) -> int:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        return int(session.scalar(select(func.count()).select_from(SyncClientMutation)) or 0)


def _transaction_status_and_version(
    sync_graph: dict[str, Any],
    transaction_id: UUID,
) -> tuple[str, int]:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        row = session.get(Transaction, transaction_id)
        assert row is not None
        return row.record_status, int(row.version)


def _planning_child_status_version(
    sync_graph: dict[str, Any],
    model: type,
    entity_id: UUID,
) -> tuple[str, int]:
    with Session(sync_graph["engine"], expire_on_commit=False, future=True) as session:
        row = session.get(model, entity_id)
        assert row is not None
        return row.record_status, int(row.version)


def _push_single_mutation(
    client: TestClient,
    mutation: dict[str, Any],
    *,
    device_id: str = "android-planning-device",
):
    return client.post(
        "/api/v1/sync/push",
        json={
            "deviceId": device_id,
            "clientSchemaVersion": 1,
            "mutations": [mutation],
        },
    )


def _domain_create_mutation(entity_type: str, entity_id: UUID) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any]] = {
        "accounts": {
            "name": "Offline Account",
            "accountType": "cash",
            "ownershipType": "personal",
            "currency": "RUB",
            "initialBalance": "10.0000",
        },
        "categories": {
            "name": "Offline Category",
            "type": "expense",
            "scope": "personal",
            "iconKey": "tag",
            "color": "#336699",
        },
        "asset_categories": {
            "name": "Offline Asset Category",
            "scopeType": "personal",
            "currency": "RUB",
            "assetType": "brokerage",
            "manualAmount": "0.0000",
            "isInvestment": True,
        },
    }
    return {
        "clientMutationId": f"mutation-{entity_type}-create",
        "entityType": entity_type,
        "entityId": str(entity_id),
        "operation": "create",
        "payload": payloads[entity_type],
    }


@pytest.mark.parametrize(
    ("entity_type", "model"),
    (
        ("accounts", Account),
        ("categories", Category),
        ("asset_categories", AssetCategory),
    ),
)
def test_sync_domain_create_idempotency_replays_stored_result(
    sync_graph: dict[str, Any],
    entity_type: str,
    model: type,
) -> None:
    entity_id = uuid4()
    body = {
        "deviceId": "android-domain-create-device",
        "clientSchemaVersion": 1,
        "mutations": [_domain_create_mutation(entity_type, entity_id)],
    }

    with _client_for_actor(sync_graph["owner"]) as client:
        first = client.post("/api/v1/sync/push", json=body)
        second = client.post("/api/v1/sync/push", json=body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["results"] == first.json()["results"]
    result = first.json()["results"][0]
    assert result["status"] == "applied"
    assert result["entityType"] == entity_type
    assert result["entityId"] == str(entity_id)
    assert result["data"]["id"] == str(entity_id)
    assert _entity_count(sync_graph, model, entity_id) == 1
    assert _sync_change_count(sync_graph, entity_id) == 1


def test_sync_push_idempotency_replays_stored_result(sync_graph: dict[str, Any]) -> None:
    entity_id = uuid4()
    body = _push_body(sync_graph, entity_id=entity_id)

    with _client_for_actor(sync_graph["owner"]) as client:
        first = client.post("/api/v1/sync/push", json=body)
        second = client.post("/api/v1/sync/push", json=body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["results"] == first.json()["results"]
    assert first.json()["results"][0]["status"] == "applied"
    assert first.json()["results"][0]["data"]["id"] == str(entity_id)
    assert _transaction_count(sync_graph, entity_id) == 1
    assert _sync_change_count(sync_graph, entity_id) == 1


@pytest.mark.parametrize("entity_type", ("capture_drafts", "screenshot_ocr", "ocr", "screenshots"))
def test_sync_push_rejects_online_only_capture_ocr_screenshot_entities(
    sync_graph: dict[str, Any],
    entity_type: str,
) -> None:
    with _client_for_actor(sync_graph["owner"]) as client:
        rejected = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-online-only-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": f"mutation-{entity_type}",
                        "entityType": entity_type,
                        "entityId": str(uuid4()),
                        "operation": "create",
                        "payload": {
                            "imageBytes": "raw image bytes must not enter sync",
                            "rawOcrText": "raw OCR text must not enter sync",
                        },
                    }
                ],
            },
        )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "ONLINE_ONLY_ENTITY_TYPE"
    assert _sync_client_mutation_count(sync_graph) == 0


def test_sync_push_idempotency_hash_mismatch_returns_conflict(
    sync_graph: dict[str, Any],
) -> None:
    entity_id = uuid4()
    body = _push_body(sync_graph, entity_id=entity_id)
    reused = deepcopy(body)
    reused["mutations"][0]["payload"]["amount"] = "99.9900"

    with _client_for_actor(sync_graph["owner"]) as client:
        first = client.post("/api/v1/sync/push", json=body)
        conflict = client.post("/api/v1/sync/push", json=reused)

    assert first.status_code == 200, first.text
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _transaction_count(sync_graph, entity_id) == 1
    assert _sync_change_count(sync_graph, entity_id) == 1


def test_sync_pull_returns_visible_changes_after_cursor(sync_graph: dict[str, Any]) -> None:
    entity_id = uuid4()
    body = _push_body(sync_graph, entity_id=entity_id)
    pull_body = {
        "deviceId": "android-test-device",
        "clientSchemaVersion": 1,
        "cursor": 0,
        "limit": 10,
        "entityTypes": ["transactions"],
    }

    with _client_for_actor(sync_graph["owner"]) as client:
        pushed = client.post("/api/v1/sync/push", json=body)
        pulled = client.post("/api/v1/sync/pull", json=pull_body)

    with _client_for_actor(sync_graph["other"]) as client:
        hidden = client.post("/api/v1/sync/pull", json=pull_body)

    assert pushed.status_code == 200, pushed.text
    assert pulled.status_code == 200, pulled.text
    pulled_body = pulled.json()
    assert pulled_body["hasMore"] is False
    assert pulled_body["nextCursor"] == pushed.json()["results"][0]["changeSeq"]
    assert len(pulled_body["changes"]) == 1
    change = pulled_body["changes"][0]
    assert change["entityType"] == "transactions"
    assert change["entityId"] == str(entity_id)
    assert change["payload"]["id"] == str(entity_id)
    assert change["payload"]["amount"] == "12.3400"
    assert hidden.status_code == 200
    assert hidden.json()["changes"] == []


def test_sync_pull_returns_online_crud_domain_changes(sync_graph: dict[str, Any]) -> None:
    with _client_for_actor(sync_graph["owner"]) as client:
        account = client.post(
            "/api/v1/accounts",
            json={
                "name": "Online Pull Account",
                "accountType": "bank",
                "ownershipType": "personal",
                "currency": "RUB",
                "initialBalance": "1.0000",
            },
        )
        category = client.post(
            "/api/v1/categories",
            json={
                "name": "Online Pull Category",
                "type": "expense",
                "scope": "personal",
                "iconKey": "tag",
                "color": "#336699",
            },
        )
        asset_category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Online Pull Asset",
                "scopeType": "personal",
                "currency": "RUB",
                "assetType": "brokerage",
                "isInvestment": True,
            },
        )
        transaction = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": sync_graph["account_id"],
                "categoryId": sync_graph["category_id"],
                "amount": "3.2100",
                "currency": "RUB",
                "transactionDate": "2026-06-14",
                "sourceType": "manual",
            },
        )
        pulled = client.post(
            "/api/v1/sync/pull",
            json={
                "deviceId": "android-online-crud-device",
                "clientSchemaVersion": 1,
                "cursor": 0,
                "limit": 20,
                "entityTypes": [
                    "accounts",
                    "categories",
                    "asset_categories",
                    "transactions",
                ],
            },
        )

    for response in (account, category, asset_category, transaction, pulled):
        assert response.status_code in {200, 201}, response.text

    ids_by_type = {
        change["entityType"]: change["entityId"] for change in pulled.json()["changes"]
    }
    assert ids_by_type["accounts"] == account.json()["data"]["id"]
    assert ids_by_type["categories"] == category.json()["data"]["id"]
    assert ids_by_type["asset_categories"] == asset_category.json()["data"]["id"]
    assert ids_by_type["transactions"] == transaction.json()["data"]["id"]
    assert all(change["clientMutationId"] is None for change in pulled.json()["changes"])

    with _client_for_actor(sync_graph["other"]) as client:
        hidden = client.post(
            "/api/v1/sync/pull",
            json={
                "deviceId": "android-online-crud-hidden-device",
                "clientSchemaVersion": 1,
                "cursor": 0,
                "limit": 20,
                "entityTypes": ["accounts", "categories", "asset_categories", "transactions"],
            },
        )

    assert hidden.status_code == 200
    assert hidden.json()["changes"] == []


def test_sync_pull_returns_tombstone_after_online_account_delete(
    sync_graph: dict[str, Any],
) -> None:
    with _client_for_actor(sync_graph["owner"]) as client:
        created = client.post(
            "/api/v1/accounts",
            json={
                "name": "Online Delete Account",
                "accountType": "cash",
                "ownershipType": "personal",
                "currency": "RUB",
                "initialBalance": "5.0000",
            },
        )
        account_id = created.json()["data"]["id"]
        deleted = client.delete(f"/api/v1/accounts/{account_id}")
        pulled = client.post(
            "/api/v1/sync/pull",
            json={
                "deviceId": "android-tombstone-device",
                "clientSchemaVersion": 1,
                "cursor": 0,
                "limit": 20,
                "entityTypes": ["accounts"],
            },
        )

    assert created.status_code == 201, created.text
    assert deleted.status_code == 204, deleted.text
    assert pulled.status_code == 200, pulled.text
    delete_changes = [
        change for change in pulled.json()["changes"] if change["changeType"] == "delete"
    ]
    assert len(delete_changes) == 1
    tombstone = delete_changes[0]
    assert tombstone["entityType"] == "accounts"
    assert tombstone["entityId"] == account_id
    assert tombstone["payload"] is None
    assert tombstone["tombstonePayload"]["id"] == account_id
    assert tombstone["tombstonePayload"]["entityType"] == "accounts"
    assert tombstone["tombstonePayload"]["version"] == 2


def test_sync_account_update_stale_base_version_is_rejected(
    sync_graph: dict[str, Any],
) -> None:
    account_id = sync_graph["account_id"]

    with _client_for_actor(sync_graph["owner"]) as client:
        stale = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-stale-account-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": "mutation-account-stale-update",
                        "entityType": "accounts",
                        "entityId": account_id,
                        "operation": "update",
                        "baseVersion": 2,
                        "payload": {"name": "Stale Offline Name"},
                    }
                ],
            },
        )

    assert stale.status_code == 200, stale.text
    result = stale.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["errorCode"] == "CONFLICTING_UPDATE"
    assert _sync_change_count(sync_graph, UUID(str(account_id))) == 0


def test_sync_account_update_rejects_offline_current_balance(
    sync_graph: dict[str, Any],
) -> None:
    account_id = sync_graph["account_id"]

    with _client_for_actor(sync_graph["owner"]) as client:
        rejected = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-account-balance-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": "mutation-account-current-balance",
                        "entityType": "accounts",
                        "entityId": account_id,
                        "operation": "update",
                        "baseVersion": 1,
                        "payload": {"currentBalance": "999.0000"},
                    }
                ],
            },
        )

    assert rejected.status_code == 200, rejected.text
    result = rejected.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["errorCode"] == "UNSUPPORTED_FIELD"
    assert _sync_change_count(sync_graph, UUID(str(account_id))) == 0


def test_sync_transaction_replay_does_not_duplicate_transaction(
    sync_graph: dict[str, Any],
) -> None:
    entity_id = uuid4()
    body = _push_body(
        sync_graph,
        entity_id=entity_id,
        client_mutation_id="mutation-create-replay",
    )

    with _client_for_actor(sync_graph["owner"]) as client:
        for _ in range(3):
            response = client.post("/api/v1/sync/push", json=body)
            assert response.status_code == 200, response.text

    assert _transaction_count(sync_graph, entity_id) == 1
    assert _sync_change_count(sync_graph, entity_id) == 1


def test_sync_transaction_update_delete_restore_lifecycle(sync_graph: dict[str, Any]) -> None:
    entity_id = uuid4()
    create_body = _push_body(
        sync_graph,
        entity_id=entity_id,
        client_mutation_id="mutation-lifecycle-create",
    )

    with _client_for_actor(sync_graph["owner"]) as client:
        created = client.post("/api/v1/sync/push", json=create_body)
        created_version = created.json()["results"][0]["serverVersion"]

        updated = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-test-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": "mutation-lifecycle-update",
                        "entityType": "transactions",
                        "entityId": str(entity_id),
                        "operation": "update",
                        "baseVersion": created_version,
                        "payload": {
                            "amount": "22.0000",
                            "description": "updated offline",
                        },
                    }
                ],
            },
        )
        updated_version = updated.json()["results"][0]["serverVersion"]

        deleted = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-test-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": "mutation-lifecycle-delete",
                        "entityType": "transactions",
                        "entityId": str(entity_id),
                        "operation": "delete",
                        "baseVersion": updated_version,
                    }
                ],
            },
        )
        deleted_version = deleted.json()["results"][0]["serverVersion"]

        restored = client.post(
            "/api/v1/sync/push",
            json={
                "deviceId": "android-test-device",
                "clientSchemaVersion": 1,
                "mutations": [
                    {
                        "clientMutationId": "mutation-lifecycle-restore",
                        "entityType": "transactions",
                        "entityId": str(entity_id),
                        "operation": "restore",
                        "baseVersion": deleted_version,
                    }
                ],
            },
        )

    for response in (created, updated, deleted, restored):
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["status"] == "applied"

    assert _sync_change_count(sync_graph, entity_id) == 4
    assert _transaction_status_and_version(sync_graph, entity_id) == ("active", 4)
    assert restored.json()["results"][0]["data"]["description"] == "updated offline"


def test_sync_planning_push_lifecycle_and_idempotency(sync_graph: dict[str, Any]) -> None:
    plan_id = uuid4()
    income_id = uuid4()
    allocation_id = uuid4()

    with _client_for_actor(sync_graph["owner"]) as client:
        create_plan_mutation = {
            "clientMutationId": "mutation-planning-plan-create",
            "entityType": "planning_plans",
            "entityId": str(plan_id),
            "operation": "create",
            "payload": {"scope": "personal", "month": "2026-12", "currency": "RUB"},
        }
        created_plan = _push_single_mutation(client, create_plan_mutation)
        replayed_plan = _push_single_mutation(client, create_plan_mutation)

        create_income_mutation = {
            "clientMutationId": "mutation-planning-income-create",
            "entityType": "planning_income_sources",
            "entityId": str(income_id),
            "operation": "create",
            "payload": {
                "planId": str(plan_id),
                "amount": "1000.0000",
                "source": "Salary",
                "dayOfMonth": 15,
            },
        }
        created_income = _push_single_mutation(client, create_income_mutation)
        replayed_income = _push_single_mutation(client, create_income_mutation)
        income_version = created_income.json()["results"][0]["serverVersion"]

        updated_income = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-income-update",
                "entityType": "planning_income_sources",
                "entityId": str(income_id),
                "operation": "update",
                "baseVersion": income_version,
                "payload": {"amount": "1200.0000", "description": "adjusted"},
            },
        )
        income_version = updated_income.json()["results"][0]["serverVersion"]

        confirm_income_mutation = {
            "clientMutationId": "mutation-planning-income-confirm",
            "entityType": "planning_income_sources",
            "entityId": str(income_id),
            "operation": "confirm",
            "baseVersion": income_version,
        }
        confirmed_income = _push_single_mutation(client, confirm_income_mutation)
        replayed_confirm = _push_single_mutation(client, confirm_income_mutation)
        income_version = confirmed_income.json()["results"][0]["serverVersion"]

        deleted_income = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-income-delete",
                "entityType": "planning_income_sources",
                "entityId": str(income_id),
                "operation": "delete",
                "baseVersion": income_version,
            },
        )

        created_allocation = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-allocation-create",
                "entityType": "planning_allocations",
                "entityId": str(allocation_id),
                "operation": "create",
                "payload": {
                    "planId": str(plan_id),
                    "targetType": "expense_category",
                    "targetId": sync_graph["category_id"],
                    "allocationMode": "amount",
                    "allocationValue": "250.0000",
                },
            },
        )
        allocation_version = created_allocation.json()["results"][0]["serverVersion"]

        updated_allocation = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-allocation-update",
                "entityType": "planning_allocations",
                "entityId": str(allocation_id),
                "operation": "update",
                "baseVersion": allocation_version,
                "payload": {"allocationValue": "300.0000", "comment": "updated"},
            },
        )
        allocation_version = updated_allocation.json()["results"][0]["serverVersion"]

        deleted_allocation = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-allocation-delete",
                "entityType": "planning_allocations",
                "entityId": str(allocation_id),
                "operation": "delete",
                "baseVersion": allocation_version,
            },
        )

    for response in (
        created_plan,
        replayed_plan,
        created_income,
        replayed_income,
        updated_income,
        confirmed_income,
        replayed_confirm,
        deleted_income,
        created_allocation,
        updated_allocation,
        deleted_allocation,
    ):
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["status"] == "applied"

    assert replayed_plan.json()["results"] == created_plan.json()["results"]
    assert replayed_income.json()["results"] == created_income.json()["results"]
    assert replayed_confirm.json()["results"] == confirmed_income.json()["results"]
    assert _entity_count(sync_graph, PlanningPlan, plan_id) == 1
    assert _sync_change_count(sync_graph, plan_id) == 1
    assert _sync_change_count(sync_graph, income_id) == 4
    assert _sync_change_count(sync_graph, allocation_id) == 3
    assert _planning_child_status_version(sync_graph, PlanningIncomeSource, income_id) == (
        "deleted",
        4,
    )
    assert _planning_child_status_version(sync_graph, PlanningAllocation, allocation_id) == (
        "deleted",
        3,
    )
    assert deleted_income.json()["results"][0]["data"]["recordStatus"] == "deleted"
    assert deleted_allocation.json()["results"][0]["data"]["recordStatus"] == "deleted"


def test_sync_planning_stale_base_version_is_rejected(sync_graph: dict[str, Any]) -> None:
    plan_id = uuid4()
    income_id = uuid4()

    with _client_for_actor(sync_graph["owner"]) as client:
        created_plan = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-stale-plan-create",
                "entityType": "planning_plans",
                "entityId": str(plan_id),
                "operation": "create",
                "payload": {"scope": "personal", "month": "2027-01", "currency": "RUB"},
            },
            device_id="android-planning-stale-device",
        )
        created_income = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-stale-income-create",
                "entityType": "planning_income_sources",
                "entityId": str(income_id),
                "operation": "create",
                "payload": {
                    "planId": str(plan_id),
                    "amount": "1000.0000",
                    "source": "Salary",
                    "dayOfMonth": 15,
                },
            },
            device_id="android-planning-stale-device",
        )
        stale = _push_single_mutation(
            client,
            {
                "clientMutationId": "mutation-planning-stale-income-update",
                "entityType": "planning_income_sources",
                "entityId": str(income_id),
                "operation": "update",
                "baseVersion": 2,
                "payload": {"amount": "1500.0000"},
            },
            device_id="android-planning-stale-device",
        )

    assert created_plan.status_code == 200, created_plan.text
    assert created_income.status_code == 200, created_income.text
    assert stale.status_code == 200, stale.text
    result = stale.json()["results"][0]
    assert result["status"] == "rejected"
    assert result["errorCode"] == "CONFLICTING_UPDATE"
    assert _sync_change_count(sync_graph, income_id) == 1
    assert _planning_child_status_version(sync_graph, PlanningIncomeSource, income_id) == (
        "active",
        1,
    )


def test_sync_pull_returns_online_planning_payload_and_tombstone(
    sync_graph: dict[str, Any],
) -> None:
    with _client_for_actor(sync_graph["owner"]) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2027-02", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        created_income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": "1000.0000",
                "source": "Salary",
                "dayOfMonth": 15,
            },
        )
        assert created_income.status_code == 201, created_income.text
        income_id = created_income.json()["data"]["id"]

        deleted_income = client.delete(f"/api/v1/planning/income-sources/{income_id}")
        pulled = client.post(
            "/api/v1/sync/pull",
            json={
                "deviceId": "android-online-planning-device",
                "clientSchemaVersion": 1,
                "cursor": 0,
                "limit": 20,
                "entityTypes": ["planning_plans", "planning_income_sources"],
            },
        )

    assert deleted_income.status_code == 204, deleted_income.text
    assert pulled.status_code == 200, pulled.text
    changes = pulled.json()["changes"]
    plan_change = next(change for change in changes if change["entityId"] == plan_id)
    delete_change = next(
        change for change in changes if change["changeType"] == "delete"
    )
    assert plan_change["entityType"] == "planning_plans"
    assert plan_change["payload"]["id"] == plan_id
    assert plan_change["payload"]["month"] == "2027-02"
    assert delete_change["entityType"] == "planning_income_sources"
    assert delete_change["entityId"] == income_id
    assert delete_change["payload"] is None
    assert delete_change["tombstonePayload"]["id"] == income_id
    assert delete_change["tombstonePayload"]["entityType"] == "planning_income_sources"
    assert delete_change["tombstonePayload"]["version"] == 2
