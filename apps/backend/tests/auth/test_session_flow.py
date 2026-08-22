from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthClientKind, AuthMembershipRecord, AuthUserRecord, TokenRecordStatus
from app.auth.rate_limits import InMemoryRateLimiter, RateLimitConfig, RateLimitKey
from app.auth.runtime import (
    AuthSessionService,
    InMemoryCredentialStore,
    get_auth_session_service,
)
from app.auth.security import (
    HmacSha256TokenHashingBackend,
    Pbkdf2Sha256PasswordHashingBackend,
    RandomTokenFactory,
)
from app.auth.session_tokens import InMemorySessionTokenStore
from app.authz import Account, AccountOwnershipType, DenialReason, MembershipStatus, canReadAccount
from app.config import Settings, get_settings
from app.main import create_app


@dataclass(frozen=True)
class AuthHarness:
    service: AuthSessionService
    sessions: InMemorySessionTokenStore
    password: str
    user_id: UUID
    active_household_id: UUID
    invited_household_id: UUID
    former_household_id: UUID


def _auth_harness() -> AuthHarness:
    password = "correct horse battery staple"
    user_id = uuid4()
    active_household_id = uuid4()
    invited_household_id = uuid4()
    former_household_id = uuid4()
    password_hasher = Pbkdf2Sha256PasswordHashingBackend()
    sessions = InMemorySessionTokenStore()
    credentials = InMemoryCredentialStore(
        users=(
            AuthUserRecord(
                id=str(user_id).upper(),
                email_normalized="owner@example.test",
                password_hash=password_hasher.hash_password(password),
                session_version=7,
                memberships=(
                    AuthMembershipRecord(
                        user_id=str(user_id).upper(),
                        household_id=str(active_household_id).upper(),
                        status=MembershipStatus.ACTIVE.value,
                    ),
                    AuthMembershipRecord(
                        user_id=str(user_id).upper(),
                        household_id=str(invited_household_id).upper(),
                        status=MembershipStatus.INVITED.value,
                    ),
                    AuthMembershipRecord(
                        user_id=str(user_id).upper(),
                        household_id=str(former_household_id).upper(),
                        status=MembershipStatus.LEFT.value,
                    ),
                ),
            ),
        )
    )
    service = AuthSessionService(
        credentials=credentials,
        sessions=sessions,
        password_hasher=password_hasher,
        token_hashing=HmacSha256TokenHashingBackend(secret=b"x" * 32),
        token_factory=RandomTokenFactory(),
        bearer_session_ttl=timedelta(hours=1),
        pwa_session_ttl=timedelta(hours=1),
    )
    return AuthHarness(
        service=service,
        sessions=sessions,
        password=password,
        user_id=user_id,
        active_household_id=active_household_id,
        invited_household_id=invited_household_id,
        former_household_id=former_household_id,
    )


def _client(
    harness: AuthHarness,
    *,
    settings: Settings | None = None,
    base_url: str = "http://testserver",
) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_auth_session_service] = lambda: harness.service
    return TestClient(app, base_url=base_url)


def _login(client: TestClient, harness: AuthHarness) -> str:
    response = _login_response(client, harness)
    return str(response["accessToken"])


def _login_response(
    client: TestClient,
    harness: AuthHarness,
    *,
    transport: str = "android_bearer",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/sessions",
        json={
            "email": "OWNER@EXAMPLE.TEST",
            "password": harness.password,
            "transport": transport,
        },
    )
    assert response.status_code == 201
    assert "__Host-finance_session" not in response.headers.get("set-cookie", "")
    assert "finance_csrf" not in response.headers.get("set-cookie", "")
    return dict(response.json())


def _pwa_login(client: TestClient, harness: AuthHarness):
    response = client.post(
        "/api/v1/sessions",
        json={
            "email": "OWNER@EXAMPLE.TEST",
            "password": harness.password,
            "transport": "pwa_cookie",
        },
    )
    assert response.status_code == 201
    return response


def _cookie_header(response, name: str) -> str:
    return next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{name}=")
    )


def test_session_routes_are_default_denied_without_bearer_token() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        response = client.get("/api/v1/sessions/current")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert "bearer" not in response.text.lower()


def test_login_failure_is_neutral_and_does_not_issue_session() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "email": "missing@example.test",
                "password": "wrong",
                "transport": "android_bearer",
            },
        )

    assert response.status_code == 401
    assert response.json()["flow"] == "login_failure"
    assert response.json()["status"] == "denied"
    assert "missing@example.test" not in response.text
    assert harness.sessions.records_for_tests() == ()


def test_login_rate_limit_returns_429_after_threshold() -> None:
    harness = _auth_harness()
    app = create_app()
    app.dependency_overrides[get_auth_session_service] = lambda: harness.service
    app.state.auth_rate_limiter = InMemoryRateLimiter(
        RateLimitConfig.default().with_overrides(
            {
                RateLimitKey.LOGIN_IP_15M: 2,
                RateLimitKey.LOGIN_ACCOUNT_15M: 2,
            }
        )
    )

    with TestClient(app) as client:
        payload = {
            "email": "missing@example.test",
            "password": "wrong",
            "transport": "android_bearer",
        }
        first = client.post("/api/v1/sessions", json=payload)
        second = client.post("/api/v1/sessions", json=payload)
        third = client.post("/api/v1/sessions", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "missing@example.test" not in third.text
    assert harness.sessions.records_for_tests() == ()


def test_authenticated_bearer_session_returns_canonical_uuid_actor_context() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        access_token = _login(client, harness)
        current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert current.status_code == 200
    actor = current.json()["actor"]
    assert actor["userId"] == str(harness.user_id)
    assert actor["userId"] == str(UUID(actor["userId"]))
    assert {item["householdId"] for item in actor["memberships"]} == {
        str(harness.active_household_id),
        str(harness.invited_household_id),
        str(harness.former_household_id),
    }
    assert {item["status"] for item in actor["memberships"]} == {
        MembershipStatus.ACTIVE.value,
        MembershipStatus.INVITED.value,
        MembershipStatus.LEFT.value,
    }

    stored = harness.sessions.records_for_tests()
    assert len(stored) == 1
    assert stored[0].session_token_hash is not None
    assert access_token not in repr(stored[0])
    assert stored[0].session_version == 7


def test_android_bearer_login_returns_refresh_token_and_stores_only_hash() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        body = _login_response(client, harness)

    refresh_token = str(body["refreshToken"])
    access_token = str(body["accessToken"])
    assert body["tokenType"] == "Bearer"
    assert access_token
    assert refresh_token
    assert refresh_token != access_token

    stored = harness.sessions.records_for_tests()
    assert len(stored) == 1
    assert stored[0].refresh_token_hash is not None
    assert stored[0].session_token_hash != access_token
    assert stored[0].refresh_token_hash != refresh_token
    assert access_token not in repr(stored[0])
    assert refresh_token not in repr(stored[0])


def test_ios_bearer_login_returns_hash_only_tokens_and_authenticates_current_session() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        body = _login_response(client, harness, transport="ios_bearer")
        access_token = str(body["accessToken"])
        refresh_token = str(body["refreshToken"])
        current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert body["tokenType"] == "Bearer"
    assert current.status_code == 200
    assert current.json()["actor"]["sessionId"] == body["actor"]["sessionId"]

    stored = harness.sessions.records_for_tests()
    assert len(stored) == 1
    assert stored[0].client_kind == AuthClientKind.IOS
    assert stored[0].session_token_hash is not None
    assert stored[0].refresh_token_hash is not None
    assert access_token not in repr(stored[0])
    assert refresh_token not in repr(stored[0])


def test_refresh_rotates_android_access_and_refresh_token() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        login_body = _login_response(client, harness)
        old_access_token = str(login_body["accessToken"])
        old_refresh_token = str(login_body["refreshToken"])
        refreshed = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": old_refresh_token},
        )
        replay = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": old_refresh_token},
        )
        old_access_current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {old_access_token}"},
        )

    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["tokenType"] == "Bearer"
    assert refreshed_body["accessToken"]
    assert refreshed_body["refreshToken"]
    assert refreshed_body["accessToken"] != old_access_token
    assert refreshed_body["refreshToken"] != old_refresh_token
    assert refreshed_body["actor"]["sessionId"] == login_body["actor"]["sessionId"]
    assert replay.status_code == 401
    assert old_access_current.status_code == 401
    assert old_refresh_token not in replay.text

    stored = harness.sessions.records_for_tests()
    assert len(stored) == 1
    assert stored[0].refresh_token_hash is not None
    assert refreshed_body["refreshToken"] not in repr(stored[0])


def test_refresh_rotates_ios_tokens_once_and_invalidates_old_access() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        login_body = _login_response(client, harness, transport="ios_bearer")
        old_access_token = str(login_body["accessToken"])
        old_refresh_token = str(login_body["refreshToken"])
        refreshed = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": old_refresh_token},
        )
        replay = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": old_refresh_token},
        )
        old_access_current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {old_access_token}"},
        )

    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["accessToken"] != old_access_token
    assert refreshed_body["refreshToken"] != old_refresh_token
    assert refreshed_body["actor"]["sessionId"] == login_body["actor"]["sessionId"]
    assert replay.status_code == 401
    assert old_access_current.status_code == 401
    assert old_refresh_token not in replay.text


def test_ios_logout_revokes_access_and_refresh_tokens() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        login_body = _login_response(client, harness, transport="ios_bearer")
        access_token = str(login_body["accessToken"])
        refresh_token = str(login_body["refreshToken"])
        logout = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        current = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        refresh = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refresh_token},
        )

    assert logout.status_code == 204
    assert current.status_code == 401
    assert refresh.status_code == 401
    assert harness.sessions.records_for_tests()[0].status == TokenRecordStatus.REVOKED


def test_unknown_auth_transport_is_rejected_without_creating_session() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "email": "OWNER@EXAMPLE.TEST",
                "password": harness.password,
                "transport": "windows_bearer",
            },
        )

    assert response.status_code == 422
    assert harness.sessions.records_for_tests() == ()


def test_refresh_with_invalid_expired_or_revoked_token_is_rejected() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        invalid = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": "invalid-refresh-token"},
        )
        login_body = _login_response(client, harness)
        refresh_token = str(login_body["refreshToken"])

        record = harness.sessions.records_for_tests()[0]
        harness.sessions._records[record.id] = replace(
            record,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        expired = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refresh_token},
        )

    assert invalid.status_code == 401
    assert expired.status_code == 401
    assert refresh_token not in expired.text

    revoked_harness = _auth_harness()
    with _client(revoked_harness) as client:
        login_body = _login_response(client, revoked_harness)
        access_token = str(login_body["accessToken"])
        refresh_token = str(login_body["refreshToken"])
        logout = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        revoked = client.post(
            "/api/v1/sessions/refresh",
            json={"refreshToken": refresh_token},
        )

    assert logout.status_code == 204
    assert revoked.status_code == 401
    assert refresh_token not in revoked.text


def test_pwa_login_sets_httponly_session_cookie_and_readable_csrf_cookie() -> None:
    harness = _auth_harness()

    with _client(harness, base_url="https://testserver") as client:
        login = _pwa_login(client, harness)
        session_token = client.cookies.get("__Host-finance_session")

    body = login.json()
    assert body["transport"] == "pwa_cookie"
    assert body["csrfToken"]
    assert "accessToken" not in body

    session_cookie = _cookie_header(login, "__Host-finance_session")
    csrf_cookie = _cookie_header(login, "finance_csrf")
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "SameSite=lax" in csrf_cookie

    stored = harness.sessions.records_for_tests()
    assert len(stored) == 1
    assert stored[0].client_kind == AuthClientKind.PWA
    assert stored[0].session_token_hash is not None
    assert stored[0].csrf_token_hash is not None
    assert session_token
    assert session_token not in repr(stored[0])
    assert body["csrfToken"] not in repr(stored[0])


def test_pwa_current_session_resolves_actor_from_cookie() -> None:
    harness = _auth_harness()

    with _client(harness, base_url="https://testserver") as client:
        _pwa_login(client, harness)
        current = client.get("/api/v1/sessions/current")

    assert current.status_code == 200
    actor = current.json()["actor"]
    assert actor["userId"] == str(harness.user_id)
    assert actor["sessionId"] == harness.sessions.records_for_tests()[0].id


def test_cookie_authenticated_unsafe_request_without_csrf_is_rejected() -> None:
    harness = _auth_harness()

    with _client(harness, base_url="https://testserver") as client:
        _pwa_login(client, harness)
        logout = client.delete("/api/v1/sessions/current")

    assert logout.status_code == 403
    assert logout.json()["error"]["code"] == "CSRF_TOKEN_INVALID"
    assert "csrf" in logout.json()["error"]["message"].lower()
    assert harness.sessions.records_for_tests()[0].status == TokenRecordStatus.ACTIVE


def test_cookie_authenticated_unsafe_request_with_csrf_is_allowed_and_clears_cookies() -> None:
    harness = _auth_harness()

    with _client(harness, base_url="https://testserver") as client:
        _pwa_login(client, harness)
        csrf_token = client.cookies.get("finance_csrf")
        logout = client.delete(
            "/api/v1/sessions/current",
            headers={"X-CSRF-Token": csrf_token or ""},
        )
        after_logout = client.get("/api/v1/sessions/current")

    assert logout.status_code == 204
    assert after_logout.status_code == 401
    assert harness.sessions.records_for_tests()[0].status == TokenRecordStatus.REVOKED
    set_cookie_headers = logout.headers.get_list("set-cookie")
    assert any(header.startswith("__Host-finance_session=") for header in set_cookie_headers)
    assert any(header.startswith("finance_csrf=") for header in set_cookie_headers)


def test_pwa_cookie_security_attributes_are_settings_driven_for_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _auth_harness()
    monkeypatch.setenv("FINANCE_BACKEND_AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("FINANCE_BACKEND_AUTH_COOKIE_SAMESITE", "strict")
    monkeypatch.setenv("FINANCE_BACKEND_AUTH_SESSION_COOKIE_NAME", "finance_session_local")
    get_settings.cache_clear()

    try:
        with _client(harness) as client:
            login = _pwa_login(client, harness)
            current = client.get("/api/v1/sessions/current")

        session_cookie = _cookie_header(login, "finance_session_local")
        csrf_cookie = _cookie_header(login, "finance_csrf")
        assert "; secure" not in session_cookie.lower()
        assert "; secure" not in csrf_cookie.lower()
        assert "SameSite=strict" in session_cookie
        assert "SameSite=strict" in csrf_cookie
        assert current.status_code == 200
    finally:
        get_settings.cache_clear()


def test_malformed_invalid_and_revoked_tokens_are_neutral() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        access_token = _login(client, harness)
        malformed = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": "Bearer token with spaces"},
        )
        invalid = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": "Bearer invalid-token"},
        )
        revoked = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        after_revoke = client.get(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert malformed.status_code == 401
    assert invalid.status_code == 401
    assert revoked.status_code == 204
    assert after_revoke.status_code == 401
    assert harness.sessions.records_for_tests()[0].status == TokenRecordStatus.REVOKED
    assert access_token not in after_revoke.text


def test_invited_and_former_memberships_are_represented_but_not_authorized() -> None:
    harness = _auth_harness()

    with _client(harness) as client:
        access_token = _login(client, harness)

    actor = harness.service.actor_for_bearer_token(access_token)
    assert actor is not None

    invited_decision = canReadAccount(
        actor,
        Account(
            id="invited-shared",
            ownership_type=AccountOwnershipType.SHARED,
            household_id=str(harness.invited_household_id),
        ),
    )
    former_decision = canReadAccount(
        actor,
        Account(
            id="former-shared",
            ownership_type=AccountOwnershipType.SHARED,
            household_id=str(harness.former_household_id),
        ),
    )

    assert invited_decision.allowed is False
    assert former_decision.allowed is False
    assert invited_decision.reason == DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE
    assert former_decision.reason == DenialReason.RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE
