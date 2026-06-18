from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import AccountOwnershipType, Actor, Membership, MembershipStatus
from app.config import get_settings
from app.db.base import Base
from app.db.models import (
    Account,
    AccountBalanceSnapshot,
    AssetCategory,
    Category,
    Household,
    SyncChange,
    SyncClient,
    SyncClientMutation,
    Transaction,
    User,
)
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url
from app.main import create_app

BASE_TIME = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
SLICE_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    AssetCategory.__table__,
    Account.__table__,
    AccountBalanceSnapshot.__table__,
    Category.__table__,
    Transaction.__table__,
    SyncClient.__table__,
    SyncChange.__table__,
    SyncClientMutation.__table__,
]


@pytest.fixture
def migration_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'investment.sqlite').as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE", "db")
    get_settings.cache_clear()
    sync_engine_for_url.cache_clear()

    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=SLICE_TABLES)

    owner_id = uuid4()
    member_id = uuid4()
    household_id = uuid4()
    existing_asset_category_id = uuid4()

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add_all(
            [
                _user(owner_id, "owner"),
                _user(member_id, "member"),
                Household(
                    id=household_id,
                    name="Investment Household",
                    created_by_user_id=owner_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
            ]
        )
        for user_id in (owner_id, member_id):
            session.add(
                DbMembership(
                    id=uuid4(),
                    household_id=household_id,
                    user_id=user_id,
                    membership_status="active",
                    joined_at=BASE_TIME,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        session.add(
            AssetCategory(
                id=existing_asset_category_id,
                name="Existing Non-investment",
                scope_type="personal",
                owner_user_id=owner_id,
                household_id=None,
                currency="RUB",
                asset_type="brokerage",
                icon_key=None,
                manual_amount=Decimal("0.0000"),
                is_investment=False,
                record_status="active",
                created_by_user_id=owner_id,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            )
        )

        accounts = SqlAlchemyAccountRepository(session)
        account_a = accounts.create(
            name="Brokerage A",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("100.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
            is_payment_account=False,
        )
        account_b = accounts.create(
            name="Brokerage B",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("200.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
            is_payment_account=False,
        )
        usd_account = accounts.create(
            name="Brokerage USD",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="USD",
            initial_balance=Decimal("300.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
            is_payment_account=False,
        )
        metal_account = accounts.create(
            name="Metal",
            account_type="metal",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("400.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
            is_payment_account=False,
        )
        shared_account = accounts.create(
            name="Shared Brokerage",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.SHARED,
            currency="RUB",
            initial_balance=Decimal("500.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=None,
            household_id=str(household_id),
            is_payment_account=False,
        )
        linked_account = accounts.create(
            name="Linked Brokerage",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("600.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
            asset_category_id=str(existing_asset_category_id),
            is_payment_account=False,
        )
        session.flush()

    try:
        yield {
            "engine": engine,
            "owner": _actor(owner_id, household_id),
            "household_id": str(household_id),
            "account_a": account_a.id,
            "account_b": account_b.id,
            "usd_account": usd_account.id,
            "metal_account": metal_account.id,
            "shared_account": shared_account.id,
            "linked_account": linked_account.id,
        }
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


def _actor(user_id: UUID, household_id: UUID) -> Actor:
    return Actor(
        user_id=str(user_id),
        request_id=f"req-{user_id}",
        memberships=(
            Membership(
                user_id=str(user_id),
                household_id=str(household_id),
                status=MembershipStatus.ACTIVE,
            ),
        ),
    )


def _migration_body(
    graph: dict[str, Any],
    *,
    asset_category_id: UUID,
    account_ids: list[str] | None = None,
    account_versions: dict[str, int] | None = None,
) -> dict[str, Any]:
    account_ids = account_ids or [graph["account_a"], graph["account_b"]]
    account_versions = account_versions or {account_id: 1 for account_id in account_ids}
    return {
        "assetCategoryId": str(asset_category_id),
        "name": "Migrated Investments",
        "icon": "briefcase",
        "color": "#336699",
        "assetType": "brokerage",
        "currency": "RUB",
        "scope": "personal",
        "accountIds": account_ids,
        "accountVersions": account_versions,
    }


def _sync_body(
    graph: dict[str, Any],
    *,
    asset_category_id: UUID,
    client_mutation_id: str = "mutation-investment-migration",
) -> dict[str, Any]:
    return {
        "deviceId": "android-investment-device",
        "clientSchemaVersion": 1,
        "mutations": [
            {
                "clientMutationId": client_mutation_id,
                "entityType": "investment_migrations",
                "entityId": str(asset_category_id),
                "operation": "create",
                "payload": _migration_body(graph, asset_category_id=asset_category_id),
            }
        ],
    }


def _account_rows(
    graph: dict[str, Any],
    *account_ids: str,
) -> dict[str, tuple[str | None, Decimal, int]]:
    with Session(graph["engine"], expire_on_commit=False, future=True) as session:
        rows = {}
        for account_id in account_ids:
            account = session.get(Account, UUID(account_id))
            assert account is not None
            rows[account_id] = (
                str(account.asset_category_id) if account.asset_category_id else None,
                Decimal(account.current_balance_amount),
                int(account.version),
            )
        return rows


def _asset_category_count(graph: dict[str, Any], asset_category_id: UUID) -> int:
    with Session(graph["engine"], expire_on_commit=False, future=True) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(AssetCategory)
                .where(AssetCategory.id == asset_category_id)
            )
            or 0
        )


def _sync_change_count(graph: dict[str, Any], entity_id: str | UUID) -> int:
    with Session(graph["engine"], expire_on_commit=False, future=True) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SyncChange)
                .where(SyncChange.entity_id == UUID(str(entity_id)))
            )
            or 0
        )


def _sync_client_mutation_count(graph: dict[str, Any]) -> int:
    with Session(graph["engine"], expire_on_commit=False, future=True) as session:
        return int(session.scalar(select(func.count()).select_from(SyncClientMutation)) or 0)


def test_rest_investment_migration_creates_category_and_links_accounts_all_or_none(
    migration_graph: dict[str, Any],
) -> None:
    asset_category_id = uuid4()

    with _client_for_actor(migration_graph["owner"]) as client:
        response = client.post(
            "/api/v1/asset-categories/investment-migrations",
            json=_migration_body(migration_graph, asset_category_id=asset_category_id),
        )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["assetCategory"]["id"] == str(asset_category_id)
    assert data["assetCategory"]["isInvestment"] is True
    assert data["assetCategory"]["manualAmount"] == "0.0000"
    assert data["assetCategory"]["iconKey"] == "briefcase"
    assert {account["assetCategoryId"] for account in data["accounts"]} == {
        str(asset_category_id)
    }

    rows = _account_rows(
        migration_graph,
        migration_graph["account_a"],
        migration_graph["account_b"],
    )
    assert rows[migration_graph["account_a"]] == (
        str(asset_category_id),
        Decimal("100.0000"),
        2,
    )
    assert rows[migration_graph["account_b"]] == (
        str(asset_category_id),
        Decimal("200.0000"),
        2,
    )
    assert _sync_change_count(migration_graph, asset_category_id) == 1
    assert _sync_change_count(migration_graph, migration_graph["account_a"]) == 1
    assert _sync_change_count(migration_graph, migration_graph["account_b"]) == 1


def test_rest_investment_migration_rejects_stale_account_version_without_writes(
    migration_graph: dict[str, Any],
) -> None:
    asset_category_id = uuid4()

    with _client_for_actor(migration_graph["owner"]) as client:
        response = client.post(
            "/api/v1/asset-categories/investment-migrations",
            json=_migration_body(
                migration_graph,
                asset_category_id=asset_category_id,
                account_versions={
                    migration_graph["account_a"]: 2,
                    migration_graph["account_b"]: 1,
                },
            ),
        )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "CONFLICTING_UPDATE"
    assert _asset_category_count(migration_graph, asset_category_id) == 0
    rows = _account_rows(
        migration_graph,
        migration_graph["account_a"],
        migration_graph["account_b"],
    )
    assert rows[migration_graph["account_a"]] == (None, Decimal("100.0000"), 1)
    assert rows[migration_graph["account_b"]] == (None, Decimal("200.0000"), 1)
    assert _sync_change_count(migration_graph, asset_category_id) == 0


@pytest.mark.parametrize(
    ("account_key", "expected_code"),
    (
        ("usd_account", "ACCOUNT_CURRENCY_MISMATCH"),
        ("shared_account", "ACCOUNT_SCOPE_MISMATCH"),
        ("linked_account", "ACCOUNT_ALREADY_LINKED_TO_ASSET_CATEGORY"),
        ("metal_account", "ACCOUNT_ASSET_TYPE_MISMATCH"),
    ),
)
def test_rest_investment_migration_rejects_mismatches_without_partial_writes(
    migration_graph: dict[str, Any],
    account_key: str,
    expected_code: str,
) -> None:
    asset_category_id = uuid4()
    account_id = migration_graph[account_key]

    with _client_for_actor(migration_graph["owner"]) as client:
        response = client.post(
            "/api/v1/asset-categories/investment-migrations",
            json=_migration_body(
                migration_graph,
                asset_category_id=asset_category_id,
                account_ids=[migration_graph["account_a"], account_id],
            ),
        )

    assert response.status_code in {409, 422}, response.text
    assert response.json()["error"]["code"] == expected_code
    assert _asset_category_count(migration_graph, asset_category_id) == 0
    rows = _account_rows(migration_graph, migration_graph["account_a"], account_id)
    assert rows[migration_graph["account_a"]] == (None, Decimal("100.0000"), 1)
    assert rows[account_id][0] != str(asset_category_id)
    assert _sync_change_count(migration_graph, asset_category_id) == 0


def test_sync_investment_migration_idempotent_replay_returns_same_result(
    migration_graph: dict[str, Any],
) -> None:
    asset_category_id = uuid4()
    body = _sync_body(migration_graph, asset_category_id=asset_category_id)

    with _client_for_actor(migration_graph["owner"]) as client:
        first = client.post("/api/v1/sync/push", json=body)
        second = client.post("/api/v1/sync/push", json=body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["results"] == first.json()["results"]
    result = first.json()["results"][0]
    assert result["status"] == "applied"
    assert result["entityType"] == "investment_migrations"
    assert result["entityId"] == str(asset_category_id)
    assert result["data"]["assetCategory"]["id"] == str(asset_category_id)
    assert _asset_category_count(migration_graph, asset_category_id) == 1
    assert _sync_change_count(migration_graph, asset_category_id) == 1
    assert _sync_change_count(migration_graph, migration_graph["account_a"]) == 1
    assert _sync_change_count(migration_graph, migration_graph["account_b"]) == 1
    assert _sync_client_mutation_count(migration_graph) == 1


def test_sync_investment_migration_hash_mismatch_preserves_existing_idempotency(
    migration_graph: dict[str, Any],
) -> None:
    asset_category_id = uuid4()
    body = _sync_body(migration_graph, asset_category_id=asset_category_id)
    reused = _sync_body(migration_graph, asset_category_id=asset_category_id)
    reused["mutations"][0]["payload"]["name"] = "Different Name"

    with _client_for_actor(migration_graph["owner"]) as client:
        first = client.post("/api/v1/sync/push", json=body)
        conflict = client.post("/api/v1/sync/push", json=reused)

    assert first.status_code == 200, first.text
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _asset_category_count(migration_graph, asset_category_id) == 1
    assert _sync_change_count(migration_graph, asset_category_id) == 1
    assert _sync_client_mutation_count(migration_graph) == 1


def test_investment_migration_is_visible_in_account_balance_reports(
    migration_graph: dict[str, Any],
) -> None:
    asset_category_id = uuid4()

    with _client_for_actor(migration_graph["owner"]) as client:
        migrated = client.post(
            "/api/v1/asset-categories/investment-migrations",
            json=_migration_body(migration_graph, asset_category_id=asset_category_id),
        )
        report = client.get(
            "/api/v1/reports/account-balances",
            params={"reportMode": "personal", "timezone": "Europe/Moscow"},
        )

    assert migrated.status_code == 201, migrated.text
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    group = next(
        item
        for item in data["assetCategoryGroups"]
        if item["assetCategoryId"] == str(asset_category_id)
    )
    assert group["accountCount"] == 2
    assert group["currentBalanceTotal"] == "300.0000"
    assert data["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "300.0000"}
    ]
