"""Session token skeleton for PWA cookies and Android bearer/refresh tokens.

Release blockers before production:
- deployment secret wiring for token hashing;
- DB-backed revocable/versioned session storage;
- CSRF binding and rotation for PWA cookie sessions;
- rotating refresh-token validation/storage for Android;
- logout/logout-all/password-reset/membership-loss revocation hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from .models import AuthClientKind, SessionStorageRecord, TokenRecordStatus
from .schemas import AndroidBearerRefreshContract, IosBearerRefreshContract, PwaCookieCsrfContract
from .security import RandomTokenFactory, TokenHashingBackend
from .service import AuthReleaseBlocker


class SessionTokenStore(Protocol):
    """Storage interface for hashed session/refresh/CSRF tokens only."""

    def store_session(self, record: SessionStorageRecord) -> SessionStorageRecord:
        """Persist a session record containing hashes, never plaintext tokens."""

    def get_session_by_session_token_hash(
        self,
        *,
        session_token_hash: str,
    ) -> SessionStorageRecord | None:
        """Fetch a stored session by a precomputed token hash."""

    def get_session_by_refresh_token_hash(
        self,
        *,
        refresh_token_hash: str,
    ) -> SessionStorageRecord | None:
        """Fetch a stored Android session by a precomputed refresh token hash."""

    def rotate_bearer_session_tokens(
        self,
        *,
        session_id: str,
        client_kind: AuthClientKind,
        old_refresh_token_hash: str,
        new_session_token_hash: str,
        new_refresh_token_hash: str,
        rotated_at: datetime,
        new_access_expires_at: datetime | None = None,
        new_expires_at: datetime | None = None,
    ) -> SessionStorageRecord | None:
        """Replace mobile bearer hashes when the old refresh hash still matches."""

    def revoke_session(self, *, session_id: str, revoked_at: datetime) -> None:
        """Revoke one stored session."""

    def revoke_user_sessions(self, *, user_id: str, revoked_at: datetime) -> None:
        """Revoke all sessions for password reset/logout-all/security events."""


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Boundary object containing plaintext tokens returned once to the client."""

    storage_record: SessionStorageRecord
    session_token: str | None = None
    refresh_token: str | None = None
    csrf_token: str | None = None
    revoke_token: str | None = None


@dataclass(slots=True)
class InMemorySessionTokenStore:
    """Hash-only process-local session store for tests and non-DB MVP wiring."""

    _records: dict[str, SessionStorageRecord] = field(default_factory=dict)

    def store_session(self, record: SessionStorageRecord) -> SessionStorageRecord:
        self._records[record.id] = record
        return record

    def get_session_by_session_token_hash(
        self,
        *,
        session_token_hash: str,
    ) -> SessionStorageRecord | None:
        for record in self._records.values():
            if record.session_token_hash == session_token_hash:
                return record
        return None

    def get_session_by_refresh_token_hash(
        self,
        *,
        refresh_token_hash: str,
    ) -> SessionStorageRecord | None:
        for record in self._records.values():
            if record.refresh_token_hash == refresh_token_hash:
                return record
        return None

    def rotate_bearer_session_tokens(
        self,
        *,
        session_id: str,
        client_kind: AuthClientKind,
        old_refresh_token_hash: str,
        new_session_token_hash: str,
        new_refresh_token_hash: str,
        rotated_at: datetime,
        new_access_expires_at: datetime | None = None,
        new_expires_at: datetime | None = None,
    ) -> SessionStorageRecord | None:
        record = self._records.get(session_id)
        if (
            record is None
            or client_kind not in (AuthClientKind.ANDROID, AuthClientKind.IOS)
            or record.client_kind != client_kind
            or record.refresh_token_hash != old_refresh_token_hash
            or record.status != TokenRecordStatus.ACTIVE
            or record.revoked_at is not None
            or record.expires_at <= rotated_at
        ):
            return None

        updated = replace(
            record,
            session_token_hash=new_session_token_hash,
            refresh_token_hash=new_refresh_token_hash,
            access_expires_at=new_access_expires_at or record.access_expires_at,
            expires_at=new_expires_at or record.expires_at,
        )
        self._records[session_id] = updated
        return updated

    def revoke_session(self, *, session_id: str, revoked_at: datetime) -> None:
        record = self._records.get(session_id)
        if record is None:
            return
        self._records[session_id] = replace(
            record,
            status=TokenRecordStatus.REVOKED,
            revoked_at=revoked_at,
        )

    def revoke_user_sessions(self, *, user_id: str, revoked_at: datetime) -> None:
        for session_id, record in tuple(self._records.items()):
            if record.user_id == user_id and record.status == TokenRecordStatus.ACTIVE:
                self._records[session_id] = replace(
                    record,
                    status=TokenRecordStatus.REVOKED,
                    revoked_at=revoked_at,
                )

    def records_for_tests(self) -> tuple[SessionStorageRecord, ...]:
        return tuple(self._records.values())


@dataclass(slots=True)
class SessionTokenService:
    store: SessionTokenStore | None = None
    token_factory: RandomTokenFactory | None = None
    hashing_backend: TokenHashingBackend | None = None
    pwa_session_ttl: timedelta = timedelta(hours=12)
    bearer_access_ttl: timedelta = timedelta(minutes=15)
    android_refresh_ttl: timedelta = timedelta(days=30)

    def pwa_contract(self) -> PwaCookieCsrfContract:
        return PwaCookieCsrfContract()

    def android_contract(self) -> AndroidBearerRefreshContract:
        return AndroidBearerRefreshContract()

    def ios_contract(self) -> IosBearerRefreshContract:
        return IosBearerRefreshContract()

    def issue_pwa_cookie_session(self, *, user_id: str, session_version: int = 1) -> IssuedSession:
        """Issue a PWA HttpOnly cookie session and CSRF token hashes."""

        store, token_factory, hashing_backend = self._required_primitives()
        now = datetime.now(UTC)
        session_token = token_factory.create_token()
        csrf_token = token_factory.create_token()
        record = SessionStorageRecord(
            id=str(uuid4()),
            user_id=user_id,
            client_kind=AuthClientKind.PWA,
            session_version=session_version,
            issued_at=now,
            expires_at=now + self.pwa_session_ttl,
            session_token_hash=hashing_backend.hash_token(session_token),
            csrf_token_hash=hashing_backend.hash_token(csrf_token),
        )
        stored = store.store_session(record)
        return IssuedSession(
            storage_record=stored,
            session_token=session_token,
            csrf_token=csrf_token,
        )

    def issue_android_tokens(self, *, user_id: str, session_version: int = 1) -> IssuedSession:
        """Issue Android opaque bearer access and rotating refresh token hashes."""

        return self.issue_bearer_tokens(
            user_id=user_id,
            client_kind=AuthClientKind.ANDROID,
            session_version=session_version,
        )

    def issue_ios_tokens(self, *, user_id: str, session_version: int = 1) -> IssuedSession:
        """Issue iOS opaque bearer access and rotating refresh token hashes."""

        return self.issue_bearer_tokens(
            user_id=user_id,
            client_kind=AuthClientKind.IOS,
            session_version=session_version,
        )

    def issue_bearer_tokens(
        self,
        *,
        user_id: str,
        client_kind: AuthClientKind,
        session_version: int = 1,
    ) -> IssuedSession:
        """Issue opaque access and rotating refresh tokens for an approved mobile client."""

        if client_kind not in (AuthClientKind.ANDROID, AuthClientKind.IOS):
            raise ValueError(f"unsupported bearer client kind: {client_kind!r}")

        store, token_factory, hashing_backend = self._required_primitives()
        now = datetime.now(UTC)
        access_token = token_factory.create_token()
        refresh_token = token_factory.create_token()
        record = SessionStorageRecord(
            id=str(uuid4()),
            user_id=user_id,
            client_kind=client_kind,
            session_version=session_version,
            issued_at=now,
            expires_at=now + self.android_refresh_ttl,
            access_expires_at=now + self.bearer_access_ttl,
            session_token_hash=hashing_backend.hash_token(access_token),
            refresh_token_hash=hashing_backend.hash_token(refresh_token),
        )
        stored = store.store_session(record)
        return IssuedSession(
            storage_record=stored,
            session_token=access_token,
            refresh_token=refresh_token,
            revoke_token=hashing_backend.hash_token(f"session-revoke:{stored.id}"),
        )

    def rotate_android_tokens(
        self,
        *,
        record: SessionStorageRecord,
        old_refresh_token_hash: str,
        rotated_at: datetime | None = None,
    ) -> IssuedSession | None:
        """Backward-compatible wrapper for Android token rotation."""

        if record.client_kind != AuthClientKind.ANDROID:
            return None
        return self.rotate_bearer_tokens(
            record=record,
            old_refresh_token_hash=old_refresh_token_hash,
            rotated_at=rotated_at,
        )

    def rotate_bearer_tokens(
        self,
        *,
        record: SessionStorageRecord,
        old_refresh_token_hash: str,
        rotated_at: datetime | None = None,
    ) -> IssuedSession | None:
        """Rotate access and refresh tokens for an approved mobile bearer session."""

        if record.client_kind not in (AuthClientKind.ANDROID, AuthClientKind.IOS):
            return None

        store, token_factory, hashing_backend = self._required_primitives()
        current_time = rotated_at or datetime.now(UTC)
        access_token = token_factory.create_token()
        refresh_token = token_factory.create_token()
        updated = store.rotate_bearer_session_tokens(
            session_id=record.id,
            client_kind=record.client_kind,
            old_refresh_token_hash=old_refresh_token_hash,
            new_session_token_hash=hashing_backend.hash_token(access_token),
            new_refresh_token_hash=hashing_backend.hash_token(refresh_token),
            rotated_at=current_time,
            new_access_expires_at=current_time + self.bearer_access_ttl,
            new_expires_at=current_time + self.android_refresh_ttl,
        )
        if updated is None:
            return None

        return IssuedSession(
            storage_record=updated,
            session_token=access_token,
            refresh_token=refresh_token,
            revoke_token=hashing_backend.hash_token(f"session-revoke:{updated.id}"),
        )

    def revoke_for_client_kind(self, *, user_id: str, client_kind: AuthClientKind) -> None:
        raise AuthReleaseBlocker(
            f"Revocation for {client_kind.value} requires real session storage and audit wiring."
        )

    def _required_primitives(
        self,
    ) -> tuple[SessionTokenStore, RandomTokenFactory, TokenHashingBackend]:
        if self.store is None or self.token_factory is None or self.hashing_backend is None:
            raise AuthReleaseBlocker(
                "Session issuance requires explicit token factory, token hashing backend, "
                "and persistent session storage wiring."
            )
        return self.store, self.token_factory, self.hashing_backend
