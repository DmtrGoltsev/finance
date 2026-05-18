from __future__ import annotations

from datetime import timedelta

import pytest

from app.auth.models import AuthClientKind, SessionStorageRecord
from app.auth.security import (
    TOKEN_LOG_REDACTION,
    AuthSecurityConfigurationError,
    HmacSha256TokenHashingBackend,
    Pbkdf2Sha256PasswordHashingBackend,
    RandomTokenFactory,
    redact_token_for_log,
)
from app.auth.service import AuthReleaseBlocker
from app.auth.session_tokens import IssuedSession, SessionTokenService


class CapturingSessionStore:
    def __init__(self) -> None:
        self.records: list[SessionStorageRecord] = []

    def store_session(self, record: SessionStorageRecord) -> SessionStorageRecord:
        self.records.append(record)
        return record

    def revoke_session(self, *, session_id: str, revoked_at) -> None:  # noqa: ANN001
        raise AssertionError("not used by this test")

    def revoke_user_sessions(self, *, user_id: str, revoked_at) -> None:  # noqa: ANN001
        raise AssertionError("not used by this test")


def _hashing_backend() -> HmacSha256TokenHashingBackend:
    return HmacSha256TokenHashingBackend(secret=b"x" * 32)


def test_random_token_factory_uses_minimum_entropy_and_unique_tokens() -> None:
    factory = RandomTokenFactory()

    first = factory.create_token()
    second = factory.create_token()

    assert first != second
    assert len(first) >= 43
    assert "\n" not in first + second


def test_token_hashing_backend_verifies_without_storing_plaintext() -> None:
    backend = _hashing_backend()

    token_hash = backend.hash_token("opaque-session-token")

    assert token_hash.startswith("hmac-sha256:v1:")
    assert "opaque-session-token" not in token_hash
    assert backend.verify_token("opaque-session-token", token_hash) is True
    assert backend.verify_token("different-token", token_hash) is False


def test_token_hashing_rejects_weak_configuration_and_empty_tokens() -> None:
    with pytest.raises(AuthSecurityConfigurationError):
        HmacSha256TokenHashingBackend(secret=b"too-short")

    with pytest.raises(AuthSecurityConfigurationError):
        RandomTokenFactory(token_bytes=16)

    with pytest.raises(ValueError):
        _hashing_backend().hash_token("")


def test_password_hashing_backend_verifies_without_storing_plaintext() -> None:
    backend = Pbkdf2Sha256PasswordHashingBackend()

    password_hash = backend.hash_password("correct horse battery staple")

    assert password_hash.startswith("pbkdf2-sha256:v1:")
    assert "correct horse battery staple" not in password_hash
    assert backend.verify_password("correct horse battery staple", password_hash) is True
    assert backend.verify_password("wrong password", password_hash) is False
    assert backend.verify_password("correct horse battery staple", "not-a-real-hash") is False


def test_password_hashing_rejects_weak_configuration_and_empty_passwords() -> None:
    with pytest.raises(AuthSecurityConfigurationError):
        Pbkdf2Sha256PasswordHashingBackend(iterations=1)

    with pytest.raises(AuthSecurityConfigurationError):
        Pbkdf2Sha256PasswordHashingBackend(salt_bytes=8)

    with pytest.raises(ValueError):
        Pbkdf2Sha256PasswordHashingBackend().hash_password("")


def test_auth_log_redaction_never_echoes_boundary_value() -> None:
    assert redact_token_for_log("raw-token") == TOKEN_LOG_REDACTION
    assert "raw-token" not in redact_token_for_log("raw-token")


def test_session_issuance_requires_explicit_primitives_and_stores_hashes_only() -> None:
    service = SessionTokenService()

    with pytest.raises(AuthReleaseBlocker):
        service.issue_pwa_cookie_session(user_id="user-1")

    store = CapturingSessionStore()
    configured = SessionTokenService(
        store=store,
        token_factory=RandomTokenFactory(),
        hashing_backend=_hashing_backend(),
        pwa_session_ttl=timedelta(hours=1),
    )

    issued = configured.issue_pwa_cookie_session(user_id="user-1")

    assert isinstance(issued, IssuedSession)
    assert len(store.records) == 1
    assert issued.storage_record.client_kind == AuthClientKind.PWA
    assert issued.storage_record.session_token_hash is not None
    assert issued.storage_record.csrf_token_hash is not None
    assert issued.session_token not in repr(store.records[0])
    assert issued.csrf_token not in repr(store.records[0])


def test_android_session_issuance_stores_access_and_refresh_hashes_only() -> None:
    store = CapturingSessionStore()
    service = SessionTokenService(
        store=store,
        token_factory=RandomTokenFactory(),
        hashing_backend=_hashing_backend(),
    )

    issued = service.issue_android_tokens(user_id="user-android")

    assert issued.storage_record.client_kind == AuthClientKind.ANDROID
    assert issued.storage_record.session_token_hash is not None
    assert issued.storage_record.refresh_token_hash is not None
    assert issued.session_token not in repr(store.records[0])
    assert issued.refresh_token not in repr(store.records[0])
