from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.auth.security import TOKEN_HASH_PREFIX, Pbkdf2Sha256PasswordHashingBackend
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models import Household, Membership, Session, User
from app.db.session import sync_engine_for_url
from app.ops.provision_initial_owner import (
    ProvisioningError,
    main,
    provision_initial_owner,
)

AUTH_TABLES = [
    User.__table__,
    Household.__table__,
    Membership.__table__,
    Session.__table__,
]
BASE_TIME = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
PASSWORD = "correct horse battery staple"


@pytest.fixture
def sqlite_settings(tmp_path: Path) -> Settings:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'provision.sqlite').as_posix()}"
    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=AUTH_TABLES)
    return Settings(database_url=database_url, environment="local")


def test_provision_initial_owner_is_auth_only_and_idempotent(
    sqlite_settings: Settings,
) -> None:
    first = provision_initial_owner(
        settings=sqlite_settings,
        email="OWNER@EXAMPLE.TEST",
        password=PASSWORD,
        display_name="Owner",
        household_name="QA Household",
        now=BASE_TIME,
    )
    second = provision_initial_owner(
        settings=sqlite_settings,
        email="owner@example.test",
        password=None,
        display_name="Owner",
        household_name="QA Household",
        now=BASE_TIME + timedelta(minutes=1),
    )

    assert first.user_created is True
    assert first.household_created is True
    assert first.membership_created is True
    assert second.user_created is False
    assert second.household_created is False
    assert second.membership_created is False
    assert second.user_id == first.user_id
    assert second.household_id == first.household_id
    assert PASSWORD not in json.dumps(asdict(first))

    engine = sync_engine_for_url(sqlite_settings.database_url)
    with engine.connect() as connection:
        assert connection.execute(select(User)).all()
        assert len(connection.execute(select(Household)).all()) == 1
        assert len(connection.execute(select(Membership)).all()) == 1
        assert connection.execute(select(Session)).all() == []


def test_rotate_password_revokes_existing_sessions(sqlite_settings: Settings) -> None:
    created = provision_initial_owner(
        settings=sqlite_settings,
        email="owner@example.test",
        password=PASSWORD,
        display_name="Owner",
        household_name="QA Household",
        now=BASE_TIME,
    )

    engine = sync_engine_for_url(sqlite_settings.database_url)
    with engine.begin() as connection:
        connection.execute(
            Session.__table__.insert().values(
                id=uuid4(),
                user_id=UUID(created.user_id),
                session_token_hash=f"{TOKEN_HASH_PREFIX}session",
                refresh_token_hash=None,
                transport="cookie",
                session_version=1,
                csrf_token_hash=None,
                status="active",
                last_seen_at=None,
                expires_at=BASE_TIME + timedelta(hours=1),
                revoked_at=None,
                revoked_reason=None,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            )
        )

    rotated = provision_initial_owner(
        settings=sqlite_settings,
        email="owner@example.test",
        password="new correct horse battery staple",
        display_name="Owner",
        household_name="QA Household",
        rotate_password=True,
        now=BASE_TIME + timedelta(minutes=5),
    )

    assert rotated.password_rotated is True
    assert rotated.active_sessions_revoked == 1

    with OrmSession(engine, expire_on_commit=False, future=True) as db_session:
        user = db_session.execute(select(User)).scalar_one()
        session = db_session.execute(select(Session)).scalar_one()

    assert user.session_version == 2
    assert Pbkdf2Sha256PasswordHashingBackend().verify_password(
        "new correct horse battery staple",
        user.password_hash,
    )
    assert session.status == "revoked"
    assert session.revoked_reason == "provision_password_rotation"


def test_production_like_provisioning_requires_confirmation_and_runtime_secret() -> None:
    settings = Settings(
        environment="production",
        database_url="postgresql+asyncpg://finance_app:secret@127.0.0.1:5432/finance",
        database_migration_policy="external",
        accounts_categories_repository_mode="db",
    )

    with pytest.raises(ProvisioningError, match="--confirm-production"):
        provision_initial_owner(
            settings=settings,
            email="owner@example.test",
            password=PASSWORD,
            display_name="Owner",
            household_name="QA Household",
        )

    with pytest.raises(ProvisioningError, match="AUTH_TOKEN_HASH_SECRET"):
        provision_initial_owner(
            settings=settings,
            email="owner@example.test",
            password=PASSWORD,
            display_name="Owner",
            household_name="QA Household",
            confirm_production=True,
        )


def test_cli_output_does_not_print_password(
    sqlite_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", sqlite_settings.database_url)
    monkeypatch.setenv("FINANCE_BACKEND_PROVISION_PASSWORD", PASSWORD)
    get_settings.cache_clear()

    try:
        exit_code = main(["--email", "owner@example.test"])
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert '"user_created": true' in captured.out
