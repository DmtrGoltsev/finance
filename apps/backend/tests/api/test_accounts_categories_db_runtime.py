from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import AccountOwnershipType, Actor, Membership, MembershipStatus
from app.categories.repository import SqlAlchemyCategoryRepository
from app.categories.schemas import CategoryScope, CategoryType
from app.config import get_settings
from app.db.base import Base
from app.db.models import Account, Category, Household, User
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url
from app.main import create_app

BASE_TIME = datetime(2026, 5, 17, 14, 0, tzinfo=UTC)
SLICE_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    Account.__table__,
    Category.__table__,
]


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


def _actor(
    user_id: UUID,
    memberships: tuple[tuple[UUID, MembershipStatus], ...] = (),
) -> Actor:
    user_id_text = str(user_id)
    return Actor(
        user_id=user_id_text,
        request_id=f"req-{user_id_text}",
        memberships=tuple(
            Membership(
                user_id=user_id_text,
                household_id=str(household_id),
                status=status,
            )
            for household_id, status in memberships
        ),
    )


@pytest.fixture
def db_runtime_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, object]]:
    db_path = tmp_path / "accounts_categories_runtime.sqlite"
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE", "db")
    get_settings.cache_clear()

    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=SLICE_TABLES)

    owner_id = uuid4()
    member_id = uuid4()
    other_id = uuid4()
    invited_id = uuid4()
    former_id = uuid4()
    household_ab_id = uuid4()
    household_c_id = uuid4()

    with engine.begin() as connection:
        from sqlalchemy.orm import Session

        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add_all(
            [
                _user(owner_id, "owner"),
                _user(member_id, "member"),
                _user(other_id, "other"),
                _user(invited_id, "invited"),
                _user(former_id, "former"),
                Household(
                    id=household_ab_id,
                    name="AB Household",
                    created_by_user_id=owner_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                Household(
                    id=household_c_id,
                    name="C Household",
                    created_by_user_id=other_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
            ]
        )
        for user_id, household_id, status in (
            (owner_id, household_ab_id, "active"),
            (member_id, household_ab_id, "active"),
            (invited_id, household_ab_id, "invited"),
            (former_id, household_ab_id, "left"),
            (other_id, household_c_id, "active"),
        ):
            session.add(
                DbMembership(
                    id=uuid4(),
                    household_id=household_id,
                    user_id=user_id,
                    membership_status=status,
                    joined_at=BASE_TIME if status == "active" else None,
                    invited_at=BASE_TIME if status == "invited" else None,
                    ended_at=BASE_TIME if status == "left" else None,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )

        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)
        owner_account = accounts.create(
            name="Owner Personal",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("10.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        member_account = accounts.create(
            name="Member Personal",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("20.0000"),
            created_by_user_id=str(member_id),
            owner_user_id=str(member_id),
            household_id=None,
        )
        shared_account = accounts.create(
            name="Shared AB",
            account_type="cash",
            ownership_type=AccountOwnershipType.SHARED,
            currency="RUB",
            initial_balance=Decimal("30.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=None,
            household_id=str(household_ab_id),
        )
        other_shared_account = accounts.create(
            name="Shared C",
            account_type="cash",
            ownership_type=AccountOwnershipType.SHARED,
            currency="RUB",
            initial_balance=Decimal("40.0000"),
            created_by_user_id=str(other_id),
            owner_user_id=None,
            household_id=str(household_c_id),
        )
        owner_category = categories.create(
            name="Owner Food",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            icon_key="tag",
            color="#336699",
            created_by_user_id=str(owner_id),
        )
        shared_category = categories.create(
            name="Shared Food",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.HOUSEHOLD,
            owner_user_id=None,
            household_id=str(household_ab_id),
            icon_key="cart",
            color="#445566",
            created_by_user_id=str(owner_id),
        )
        other_shared_category = categories.create(
            name="Other Shared",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.HOUSEHOLD,
            owner_user_id=None,
            household_id=str(household_c_id),
            icon_key="tag",
            color="#112233",
            created_by_user_id=str(other_id),
        )
        session.flush()

    try:
        yield {
            "owner": _actor(owner_id, ((household_ab_id, MembershipStatus.ACTIVE),)),
            "member": _actor(member_id, ((household_ab_id, MembershipStatus.ACTIVE),)),
            "other": _actor(other_id, ((household_c_id, MembershipStatus.ACTIVE),)),
            "invited": _actor(invited_id, ((household_ab_id, MembershipStatus.INVITED),)),
            "former": _actor(former_id, ((household_ab_id, MembershipStatus.LEFT),)),
            "household_ab_id": str(household_ab_id),
            "owner_account_id": owner_account.id,
            "member_account_id": member_account.id,
            "shared_account_id": shared_account.id,
            "other_shared_account_id": other_shared_account.id,
            "owner_category_id": owner_category.id,
            "shared_category_id": shared_category.id,
            "other_shared_category_id": other_shared_category.id,
        }
    finally:
        engine.dispose()
        get_settings.cache_clear()
        sync_engine_for_url.cache_clear()


def _ids(body: dict[str, object]) -> set[str]:
    return {str(item["id"]) for item in body["items"]}  # type: ignore[index]


def _assert_uuid_text(value: object) -> None:
    UUID(str(value))


def test_db_backed_routes_preserve_accounts_categories_privacy_matrix(
    db_runtime_graph: dict[str, object],
) -> None:
    owner = db_runtime_graph["owner"]
    member = db_runtime_graph["member"]
    other = db_runtime_graph["other"]
    invited = db_runtime_graph["invited"]
    former = db_runtime_graph["former"]

    owner_account_ids = {
        str(db_runtime_graph["owner_account_id"]),
        str(db_runtime_graph["shared_account_id"]),
    }
    member_account_ids = {
        str(db_runtime_graph["member_account_id"]),
        str(db_runtime_graph["shared_account_id"]),
    }
    other_account_ids = {str(db_runtime_graph["other_shared_account_id"])}
    owner_category_ids = {
        str(db_runtime_graph["owner_category_id"]),
        str(db_runtime_graph["shared_category_id"]),
    }
    other_category_ids = {str(db_runtime_graph["other_shared_category_id"])}

    for actor, account_ids, category_ids in (
        (owner, owner_account_ids, owner_category_ids),
        (member, member_account_ids, {str(db_runtime_graph["shared_category_id"])}),
        (other, other_account_ids, other_category_ids),
        (invited, set(), set()),
        (former, set(), set()),
    ):
        with _client_for_actor(actor) as client:  # type: ignore[arg-type]
            accounts = client.get("/api/v1/accounts")
            categories = client.get("/api/v1/categories")
            accounts_autocomplete = client.get("/api/v1/accounts/autocomplete")
            categories_autocomplete = client.get("/api/v1/categories/autocomplete")

        assert accounts.status_code == 200
        assert categories.status_code == 200
        assert _ids(accounts.json()) == account_ids
        assert _ids(categories.json()) == category_ids
        assert _ids(accounts_autocomplete.json()).issubset(account_ids)
        assert _ids(categories_autocomplete.json()).issubset(category_ids)
        assert "totalCount" not in accounts.text + categories.text


def test_db_backed_routes_keep_missing_and_inaccessible_direct_ids_neutral(
    db_runtime_graph: dict[str, object],
) -> None:
    member = db_runtime_graph["member"]
    owner_account_id = db_runtime_graph["owner_account_id"]
    owner_category_id = db_runtime_graph["owner_category_id"]

    with _client_for_actor(member) as client:  # type: ignore[arg-type]
        hidden_account = client.get(f"/api/v1/accounts/{owner_account_id}")
        missing_account = client.get(f"/api/v1/accounts/{uuid4()}")
        hidden_category = client.get(f"/api/v1/categories/{owner_category_id}")
        missing_category = client.get(f"/api/v1/categories/{uuid4()}")

    assert hidden_account.status_code == missing_account.status_code == 404
    assert hidden_account.json()["error"]["code"] == missing_account.json()["error"]["code"]
    assert hidden_account.json()["error"]["message"] == missing_account.json()["error"]["message"]
    assert str(owner_account_id) not in hidden_account.text

    assert hidden_category.status_code == missing_category.status_code == 404
    assert hidden_category.json() == missing_category.json()
    assert str(owner_category_id) not in hidden_category.text


def test_db_backed_routes_persist_across_app_restarts(
    db_runtime_graph: dict[str, object],
) -> None:
    owner = db_runtime_graph["owner"]
    household_ab_id = db_runtime_graph["household_ab_id"]

    with _client_for_actor(owner) as client:  # type: ignore[arg-type]
        account_response = client.post(
            "/api/v1/accounts",
            json={
                "name": "Restart Proof Account",
                "accountType": "bank",
                "ownershipType": "personal",
                "currency": "RUB",
                "initialBalance": "99.0000",
            },
        )
        category_response = client.post(
            "/api/v1/categories",
            json={
                "name": "Restart Proof Category",
                "type": "expense",
                "scope": "household",
                "householdId": household_ab_id,
                "iconKey": "tag",
                "color": "#224466",
            },
        )

    assert account_response.status_code == 201
    assert category_response.status_code == 201
    account_id = account_response.json()["data"]["id"]
    category_id = category_response.json()["data"]["id"]

    with _client_for_actor(owner) as restarted_client:  # type: ignore[arg-type]
        persisted_account = restarted_client.get(f"/api/v1/accounts/{account_id}")
        persisted_category = restarted_client.get(f"/api/v1/categories/{category_id}")

    assert persisted_account.status_code == 200
    assert persisted_account.json()["data"]["name"] == "Restart Proof Account"
    assert persisted_category.status_code == 200
    assert persisted_category.json()["data"]["name"] == "Restart Proof Category"


def test_db_backed_routes_cover_create_update_archive_restore_delete_contracts(
    db_runtime_graph: dict[str, object],
) -> None:
    owner = db_runtime_graph["owner"]
    invited = db_runtime_graph["invited"]
    household_ab_id = db_runtime_graph["household_ab_id"]

    with _client_for_actor(owner) as client:  # type: ignore[arg-type]
        personal_account = client.post(
            "/api/v1/accounts",
            json={
                "name": "DB Personal Lifecycle",
                "accountType": "bank",
                "ownershipType": "personal",
                "currency": "RUB",
                "initialBalance": "12.3400",
            },
        )
        shared_account = client.post(
            "/api/v1/accounts",
            json={
                "name": "DB Shared Lifecycle",
                "accountType": "cash",
                "ownershipType": "shared",
                "householdId": household_ab_id,
                "currency": "RUB",
                "initialBalance": "1.0000",
            },
        )
        personal_category = client.post(
            "/api/v1/categories",
            json={
                "name": "DB Personal Category",
                "type": "expense",
                "scope": "personal",
                "iconKey": "tag",
                "color": "#112233",
            },
        )
        household_category = client.post(
            "/api/v1/categories",
            json={
                "name": "DB Household Category",
                "type": "income",
                "scope": "household",
                "householdId": household_ab_id,
            },
        )

    with _client_for_actor(invited) as invited_client:  # type: ignore[arg-type]
        denied_shared_account = invited_client.post(
            "/api/v1/accounts",
            json={
                "name": "Denied Shared Account",
                "accountType": "cash",
                "ownershipType": "shared",
                "householdId": household_ab_id,
                "currency": "RUB",
                "initialBalance": "1.0000",
            },
        )
        denied_household_category = invited_client.post(
            "/api/v1/categories",
            json={
                "name": "Denied Household Category",
                "type": "expense",
                "scope": "household",
                "householdId": household_ab_id,
            },
        )

    assert personal_account.status_code == 201
    assert shared_account.status_code == 201
    assert personal_category.status_code == 201
    assert household_category.status_code == 201
    assert denied_shared_account.status_code == 404
    assert denied_household_category.status_code == 404

    account_id = personal_account.json()["data"]["id"]
    category_id = personal_category.json()["data"]["id"]
    for value in (
        account_id,
        category_id,
        personal_account.json()["data"]["ownerUserId"],
        personal_category.json()["data"]["ownerUserId"],
        shared_account.json()["data"]["householdId"],
        household_category.json()["data"]["householdId"],
    ):
        _assert_uuid_text(value)

    with _client_for_actor(owner) as client:  # type: ignore[arg-type]
        updated_account = client.patch(
            f"/api/v1/accounts/{account_id}",
            json={"name": "DB Personal Lifecycle Updated", "accountType": "deposit"},
        )
        blocked_account_scope_update = client.patch(
            f"/api/v1/accounts/{account_id}",
            json={
                "ownershipType": "shared",
                "householdId": household_ab_id,
            },
        )
        account_after_blocked_scope_update = client.get(f"/api/v1/accounts/{account_id}")

        updated_category = client.patch(
            f"/api/v1/categories/{category_id}",
            json={"name": "DB Personal Category Updated", "iconKey": "fork"},
        )
        blocked_category_scope_update = client.patch(
            f"/api/v1/categories/{category_id}",
            json={
                "scope": "household",
                "householdId": household_ab_id,
            },
        )
        category_after_blocked_scope_update = client.get(f"/api/v1/categories/{category_id}")

        archived_account = client.post(f"/api/v1/accounts/{account_id}/archive")
        blocked_archived_account_update = client.patch(
            f"/api/v1/accounts/{account_id}",
            json={"name": "Should Stay Archived"},
        )
        restored_account = client.post(f"/api/v1/accounts/{account_id}/restore")
        deleted_account = client.delete(f"/api/v1/accounts/{account_id}")
        account_after_delete = client.get(f"/api/v1/accounts/{account_id}")

        archived_category = client.post(f"/api/v1/categories/{category_id}/archive")
        blocked_archived_category_update = client.patch(
            f"/api/v1/categories/{category_id}",
            json={"name": "Should Stay Archived"},
        )
        restored_category = client.post(f"/api/v1/categories/{category_id}/restore")
        deleted_category = client.delete(f"/api/v1/categories/{category_id}")
        category_after_delete = client.get(f"/api/v1/categories/{category_id}")

    assert updated_account.status_code == 200
    assert updated_account.json()["data"]["name"] == "DB Personal Lifecycle Updated"
    assert blocked_account_scope_update.status_code == 422
    assert account_after_blocked_scope_update.status_code == 200
    account_after_block = account_after_blocked_scope_update.json()["data"]
    assert account_after_block["ownershipType"] == "personal"
    assert account_after_block["householdId"] is None

    assert updated_category.status_code == 200
    assert updated_category.json()["data"]["name"] == "DB Personal Category Updated"
    assert blocked_category_scope_update.status_code == 422
    assert category_after_blocked_scope_update.status_code == 200
    category_after_block = category_after_blocked_scope_update.json()["data"]
    assert category_after_block["scope"] == "personal"
    assert category_after_block["householdId"] is None

    assert archived_account.status_code == 200
    assert archived_account.json()["data"]["status"] == "archived"
    assert blocked_archived_account_update.status_code == 409
    assert restored_account.status_code == 200
    assert restored_account.json()["data"]["status"] == "active"
    assert deleted_account.status_code == 204
    assert account_after_delete.status_code == 404

    assert archived_category.status_code == 200
    assert archived_category.json()["data"]["status"] == "archived"
    assert blocked_archived_category_update.status_code == 409
    assert restored_category.status_code == 200
    assert restored_category.json()["data"]["status"] == "active"
    assert deleted_category.status_code == 204
    assert category_after_delete.status_code == 404
