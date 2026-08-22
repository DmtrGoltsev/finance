from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.rate_limits import InMemoryRateLimiter, RateLimitConfig, RateLimitKey
from app.auth.runtime import get_auth_session_service
from app.auth.security import Pbkdf2Sha256PasswordHashingBackend
from app.config import get_settings
from app.db.base import Base
from app.db.models import Account, Category, Household, Membership, Session, User
from app.db.session import sync_engine_for_url, sync_session_factory_for_settings
from app.main import create_app

REGISTRATION_TABLES = [
    User.__table__,
    Household.__table__,
    Membership.__table__,
    Account.__table__,
    Category.__table__,
    Session.__table__,
]
PASSWORD = "correct horse battery staple"


@pytest.fixture
def registration_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'registration.sqlite').as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET", "r" * 32)
    get_settings.cache_clear()
    get_auth_session_service.cache_clear()

    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=REGISTRATION_TABLES)

    with TestClient(create_app(), base_url="https://testserver") as client:
        yield client

    get_auth_session_service.cache_clear()
    get_settings.cache_clear()
    sync_engine_for_url.cache_clear()


def test_android_bearer_registration_creates_active_user_and_token_current_session(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(
        "/api/v1/users",
        json={
            "email": "  NEW.OWNER@EXAMPLE.TEST ",
            "password": PASSWORD,
            "displayName": "New Owner",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["accessToken"]
    assert body["refreshToken"]
    assert body["expiresAt"]
    assert body["actor"]["userId"] == str(UUID(body["actor"]["userId"]))
    assert body["actor"]["memberships"] == []

    current = registration_client.get(
        "/api/v1/sessions/current",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )

    assert current.status_code == 200
    assert current.json()["actor"]["userId"] == body["actor"]["userId"]

    factory = sync_session_factory_for_settings(get_settings())
    with factory() as session:
        users = session.execute(select(User)).scalars().all()
        households = session.execute(select(Household)).scalars().all()
        memberships = session.execute(select(Membership)).scalars().all()
        sessions = session.execute(select(Session)).scalars().all()
        accounts = session.execute(select(Account)).scalars().all()
        categories = session.execute(select(Category)).scalars().all()

    assert len(users) == 1
    assert users[0].email_normalized == "new.owner@example.test"
    assert users[0].display_name == "New Owner"
    assert users[0].auth_status == "active"
    assert users[0].record_status == "active"
    assert users[0].password_hash != PASSWORD
    assert Pbkdf2Sha256PasswordHashingBackend().verify_password(PASSWORD, users[0].password_hash)
    assert households == []
    assert memberships == []
    assert len(sessions) == 1
    assert sessions[0].refresh_token_hash is not None
    assert sessions[0].refresh_token_hash != body["refreshToken"]
    assert body["refreshToken"] not in repr(sessions[0])
    assert accounts == []
    assert categories == []


def test_ios_bearer_registration_creates_ios_session_and_supports_refresh(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(
        "/api/v1/users",
        json={
            "email": "ios.owner@example.test",
            "password": PASSWORD,
            "displayName": "iOS Owner",
            "transport": "ios_bearer",
            "deviceName": "iPhone",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["accessToken"]
    assert body["refreshToken"]

    current = registration_client.get(
        "/api/v1/sessions/current",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )
    refreshed = registration_client.post(
        "/api/v1/sessions/refresh",
        json={"refreshToken": body["refreshToken"]},
    )

    assert current.status_code == 200
    assert refreshed.status_code == 200
    assert refreshed.json()["actor"]["sessionId"] == body["actor"]["sessionId"]

    factory = sync_session_factory_for_settings(get_settings())
    with factory() as session:
        stored_sessions = session.execute(select(Session)).scalars().all()

    assert len(stored_sessions) == 1
    assert stored_sessions[0].transport == "ios_bearer"


def test_registration_duplicate_email_returns_neutral_accepted_without_token(
    registration_client: TestClient,
) -> None:
    payload = {
        "email": "duplicate@example.test",
        "password": PASSWORD,
        "displayName": "Duplicate",
    }
    first = registration_client.post("/api/v1/users", json=payload)
    second = registration_client.post(
        "/api/v1/users",
        json={**payload, "email": " DUPLICATE@EXAMPLE.TEST "},
    )

    assert first.status_code == 201
    assert second.status_code == 202
    body = second.json()
    assert body == {
        "registrationAccepted": True,
        "message": "If the request can be processed, registration will continue.",
        "requestId": "request-unavailable",
    }
    assert "accessToken" not in body
    assert "actor" not in body
    public_text = second.text.lower()
    assert "duplicate@example.test" not in second.text
    assert "already" not in public_text
    assert "conflict" not in public_text
    assert "exists" not in public_text

    factory = sync_session_factory_for_settings(get_settings())
    with factory() as session:
        assert len(session.execute(select(User)).scalars().all()) == 1
        assert len(session.execute(select(Session)).scalars().all()) == 1


def test_registration_rate_limit_returns_429_after_threshold(
    registration_client: TestClient,
) -> None:
    registration_client.app.state.auth_rate_limiter = InMemoryRateLimiter(
        RateLimitConfig.default().with_overrides(
            {
                RateLimitKey.REGISTRATION_IP_HOUR: 2,
                RateLimitKey.REGISTRATION_EMAIL_HOUR: 2,
            }
        )
    )
    payload = {
        "email": "limited@example.test",
        "password": PASSWORD,
        "displayName": "Limited",
    }

    first = registration_client.post("/api/v1/users", json=payload)
    second = registration_client.post("/api/v1/users", json=payload)
    third = registration_client.post("/api/v1/users", json=payload)

    assert first.status_code == 201
    assert second.status_code == 202
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "limited@example.test" not in third.text
    assert "accessToken" not in third.text


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "not-an-email", "password": PASSWORD}, "email"),
        ({"email": "valid@example.test", "password": "too-short"}, "password"),
        ({"email": "valid@example.test", "password": PASSWORD, "unexpected": True}, "unexpected"),
    ],
)
def test_registration_rejects_invalid_email_password_and_extra_fields(
    registration_client: TestClient,
    payload: dict[str, object],
    field: str,
) -> None:
    response = registration_client.post("/api/v1/users", json=payload)

    assert response.status_code == 422
    assert field in response.text
    assert str(payload.get("password")) not in response.text


def test_pwa_cookie_registration_sets_cookie_and_csrf_session(
    registration_client: TestClient,
) -> None:
    response = registration_client.post(
        "/api/v1/users",
        json={
            "email": "pwa@example.test",
            "password": PASSWORD,
            "displayName": "PWA User",
            "transport": "pwa_cookie",
            "deviceName": "Browser",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transport"] == "pwa_cookie"
    assert body["csrfToken"]
    assert "accessToken" not in body
    assert registration_client.cookies.get("__Host-finance_session")
    assert registration_client.cookies.get("finance_csrf")

    current = registration_client.get("/api/v1/sessions/current")

    assert current.status_code == 200
    assert current.json()["actor"]["userId"] == body["actor"]["userId"]
