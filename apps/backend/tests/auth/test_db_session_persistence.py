from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from app.auth.db_stores import SqlAlchemySessionTokenStore
from app.auth.models import AuthClientKind, SessionStorageRecord
from app.auth.runtime import get_auth_session_service
from app.auth.security import TOKEN_HASH_PREFIX, Pbkdf2Sha256PasswordHashingBackend
from app.authz import MembershipStatus
from app.config import get_settings
from app.db.base import Base
from app.db.models import Household, Session, User
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url, sync_session_factory_for_settings
from app.main import create_app

BASE_TIME = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)
AUTH_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    Session.__table__,
]


@dataclass(frozen=True)
class DbAuthRuntime:
    database_url: str
    password: str
    user_id: UUID
    active_household_id: UUID
    invited_household_id: UUID
    former_household_id: UUID


@pytest.fixture
def db_auth_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[DbAuthRuntime]:
    db_path = tmp_path / "auth_runtime.sqlite"
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET", "s" * 32)
    get_settings.cache_clear()
    get_auth_session_service.cache_clear()

    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=AUTH_TABLES)

    password = "correct horse battery staple"
    password_hash = Pbkdf2Sha256PasswordHashingBackend().hash_password(password)
    user_id = uuid4()
    active_household_id = uuid4()
    invited_household_id = uuid4()
    former_household_id = uuid4()

    with OrmSession(engine, expire_on_commit=False, future=True) as session:
        session.add(
            User(
                id=user_id,
                email_normalized="owner@example.test",
                password_hash=password_hash,
                display_name="Owner",
                auth_status="active",
                record_status="active",
                session_version=11,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            )
        )
        for household_id, name in (
            (active_household_id, "Active"),
            (invited_household_id, "Invited"),
            (former_household_id, "Former"),
        ):
            session.add(
                Household(
                    id=household_id,
                    name=name,
                    created_by_user_id=user_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        for household_id, status in (
            (active_household_id, MembershipStatus.ACTIVE.value),
            (invited_household_id, MembershipStatus.INVITED.value),
            (former_household_id, MembershipStatus.LEFT.value),
        ):
            session.add(
                DbMembership(
                    id=uuid4(),
                    household_id=household_id,
                    user_id=user_id,
                    membership_status=status,
                    joined_at=BASE_TIME if status == MembershipStatus.ACTIVE.value else None,
                    invited_at=BASE_TIME if status == MembershipStatus.INVITED.value else None,
                    ended_at=BASE_TIME if status == MembershipStatus.LEFT.value else None,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )
        session.commit()

    yield DbAuthRuntime(
        database_url=database_url,
        password=password,
        user_id=user_id,
        active_household_id=active_household_id,
        invited_household_id=invited_household_id,
        former_household_id=former_household_id,
    )

    get_auth_session_service.cache_clear()
    get_settings.cache_clear()
    sync_engine_for_url.cache_clear()


def _recreated_client() -> TestClient:
    get_auth_session_service.cache_clear()
    return TestClient(create_app())


def test_db_backed_login_current_and_logout_survive_auth_store_recreation(
    db_auth_runtime: DbAuthRuntime,
) -> None:
    with _recreated_client() as client:
        login = client.post(
            "/api/v1/sessions",
            json={
                "email": "OWNER@EXAMPLE.TEST",
                "password": db_auth_runtime.password,
                "transport": "android_bearer",
            },
        )

    assert login.status_code == 201
    login_body = login.json()
    access_token = login_body["accessToken"]
    refresh_token = login_body["refreshToken"]
    assert login_body["tokenType"] == "Bearer"
    assert login_body["actor"]["userId"] == str(db_auth_runtime.user_id)
    assert login_body["actor"]["userId"] == str(UUID(login_body["actor"]["userId"]))

    with _recreated_client() as client:
        current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert current.status_code == 200
    actor = current.json()["actor"]
    assert actor["userId"] == str(db_auth_runtime.user_id)
    assert actor["sessionId"] == login_body["actor"]["sessionId"]
    assert {item["householdId"] for item in actor["memberships"]} == {
        str(db_auth_runtime.active_household_id),
        str(db_auth_runtime.invited_household_id),
        str(db_auth_runtime.former_household_id),
    }
    assert {item["status"] for item in actor["memberships"]} == {
        MembershipStatus.ACTIVE.value,
        MembershipStatus.INVITED.value,
        MembershipStatus.LEFT.value,
    }

    with _recreated_client() as client:
        refreshed = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refresh_token},
        )
        old_refresh_replay = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refresh_token},
        )

    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    refreshed_access_token = refreshed_body["accessToken"]
    refreshed_refresh_token = refreshed_body["refreshToken"]
    assert refreshed_access_token != access_token
    assert refreshed_refresh_token != refresh_token
    assert refreshed_body["actor"]["sessionId"] == login_body["actor"]["sessionId"]
    assert old_refresh_replay.status_code == 401

    with _recreated_client() as client:
        logout = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {refreshed_access_token}"},
        )

    assert logout.status_code == 204

    with _recreated_client() as client:
        after_logout = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {refreshed_access_token}"},
        )
        refresh_after_logout = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refreshed_refresh_token},
        )

    assert after_logout.status_code == 401
    assert refresh_after_logout.status_code == 401
    assert refreshed_access_token not in after_logout.text

    settings = get_settings()
    factory = sync_session_factory_for_settings(settings)
    with factory() as session:
        stored = session.execute(select(Session)).scalars().all()

    assert len(stored) == 1
    stored_session = stored[0]
    stored_token_fields = " ".join(
        str(value)
        for value in (
            stored_session.session_token_hash,
            stored_session.refresh_token_hash,
            stored_session.csrf_token_hash,
            stored_session.revoked_reason,
        )
    )
    assert stored_session.session_token_hash.startswith(TOKEN_HASH_PREFIX)
    assert stored_session.refresh_token_hash.startswith(TOKEN_HASH_PREFIX)
    assert access_token not in stored_token_fields
    assert refresh_token not in stored_token_fields
    assert refreshed_access_token not in stored_token_fields
    assert refreshed_refresh_token not in stored_token_fields
    assert stored_session.status == "revoked"


def test_sqlalchemy_session_store_rejects_plaintext_token_fields(
    db_auth_runtime: DbAuthRuntime,
) -> None:
    settings = get_settings()
    factory: sessionmaker[OrmSession] = sync_session_factory_for_settings(settings)
    store = SqlAlchemySessionTokenStore(factory)

    with pytest.raises(ValueError, match="approved auth token hash"):
        store.store_session(
            SessionStorageRecord(
                id=str(uuid4()),
                user_id=str(db_auth_runtime.user_id),
                client_kind=AuthClientKind.ANDROID,
                session_version=1,
                issued_at=BASE_TIME,
                expires_at=BASE_TIME + timedelta(hours=1),
                session_token_hash="plaintext-token",
                refresh_token_hash=f"{TOKEN_HASH_PREFIX}refresh",
            )
        )

    with factory() as session:
        assert session.execute(select(Session)).scalars().all() == []


def test_sqlalchemy_refresh_rotation_rejects_stale_expected_hash(
    db_auth_runtime: DbAuthRuntime,
) -> None:
    settings = get_settings()
    factory: sessionmaker[OrmSession] = sync_session_factory_for_settings(settings)
    store = SqlAlchemySessionTokenStore(factory)
    session_id = str(uuid4())
    old_access_hash = f"{TOKEN_HASH_PREFIX}old-access"
    old_refresh_hash = f"{TOKEN_HASH_PREFIX}old-refresh"
    first_access_hash = f"{TOKEN_HASH_PREFIX}first-access"
    first_refresh_hash = f"{TOKEN_HASH_PREFIX}first-refresh"
    second_access_hash = f"{TOKEN_HASH_PREFIX}second-access"
    second_refresh_hash = f"{TOKEN_HASH_PREFIX}second-refresh"

    stored = store.store_session(
        SessionStorageRecord(
            id=session_id,
            user_id=str(db_auth_runtime.user_id),
            client_kind=AuthClientKind.ANDROID,
            session_version=1,
            issued_at=BASE_TIME,
            expires_at=BASE_TIME + timedelta(hours=1),
            session_token_hash=old_access_hash,
            refresh_token_hash=old_refresh_hash,
        )
    )

    first_rotation = store.rotate_android_session_tokens(
        session_id=stored.id,
        old_refresh_token_hash=old_refresh_hash,
        new_session_token_hash=first_access_hash,
        new_refresh_token_hash=first_refresh_hash,
        rotated_at=BASE_TIME + timedelta(minutes=1),
    )
    stale_second_rotation = store.rotate_android_session_tokens(
        session_id=stored.id,
        old_refresh_token_hash=old_refresh_hash,
        new_session_token_hash=second_access_hash,
        new_refresh_token_hash=second_refresh_hash,
        rotated_at=BASE_TIME + timedelta(minutes=2),
    )

    assert first_rotation is not None
    assert first_rotation.session_token_hash == first_access_hash
    assert first_rotation.refresh_token_hash == first_refresh_hash
    assert stale_second_rotation is None

    with factory() as session:
        row = session.execute(
            select(Session).where(Session.id == UUID(session_id))
        ).scalar_one()

    assert row.session_token_hash == first_access_hash
    assert row.refresh_token_hash == first_refresh_hash
    assert row.session_token_hash != second_access_hash
    assert row.refresh_token_hash != second_refresh_hash


def test_sqlalchemy_refresh_rotation_atomically_extends_expiry(
    db_auth_runtime: DbAuthRuntime,
) -> None:
    settings = get_settings()
    session_factory: sessionmaker[OrmSession] = sync_session_factory_for_settings(settings)
    store = SqlAlchemySessionTokenStore(session_factory)
    old_refresh_hash = f"{TOKEN_HASH_PREFIX}old-expiry-refresh"
    new_access_hash = f"{TOKEN_HASH_PREFIX}new-expiry-access"
    new_refresh_hash = f"{TOKEN_HASH_PREFIX}new-expiry-refresh"
    original_expiry = BASE_TIME + timedelta(hours=1)
    renewed_expiry = BASE_TIME + timedelta(hours=13)
    record = SessionStorageRecord(
        id=str(uuid4()),
        user_id=str(db_auth_runtime.user_id),
        client_kind=AuthClientKind.IOS,
        session_version=1,
        issued_at=BASE_TIME,
        expires_at=original_expiry,
        session_token_hash=f"{TOKEN_HASH_PREFIX}old-expiry-access",
        refresh_token_hash=old_refresh_hash,
    )
    store.store_session(record)

    rotated = store.rotate_bearer_session_tokens(
        session_id=record.id,
        client_kind=AuthClientKind.IOS,
        old_refresh_token_hash=old_refresh_hash,
        new_session_token_hash=new_access_hash,
        new_refresh_token_hash=new_refresh_hash,
        rotated_at=BASE_TIME + timedelta(hours=1),
        new_expires_at=renewed_expiry,
    )
    stale = store.rotate_bearer_session_tokens(
        session_id=record.id,
        client_kind=AuthClientKind.IOS,
        old_refresh_token_hash=old_refresh_hash,
        new_session_token_hash=f"{TOKEN_HASH_PREFIX}stale-access",
        new_refresh_token_hash=f"{TOKEN_HASH_PREFIX}stale-refresh",
        rotated_at=BASE_TIME + timedelta(hours=2),
        new_expires_at=BASE_TIME + timedelta(hours=14),
    )

    assert rotated is not None
    assert rotated.expires_at == renewed_expiry
    assert stale is None
    with session_factory() as session:
        row = session.get(Session, UUID(record.id))
    assert row is not None
    assert row.expires_at.replace(tzinfo=UTC) == renewed_expiry
    assert row.refresh_token_hash == new_refresh_hash
