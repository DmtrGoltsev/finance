"""Mounted auth/session runtime for the MVP bearer-token foundation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol

from app.authz import Actor, Membership, MembershipStatus
from app.config import get_settings
from app.db.session import sync_session_factory_for_settings

from .db_stores import SqlAlchemyCredentialStore, SqlAlchemySessionTokenStore
from .identifiers import canonical_membership, canonical_uuid_text, normalize_email
from .models import AuthClientKind, AuthUserRecord, SessionStorageRecord, TokenRecordStatus
from .schemas import AuthTransport, LoginRequest, NeutralPublicResponse
from .security import (
    AuthSecurityConfigurationError,
    HmacSha256TokenHashingBackend,
    PasswordHashingBackend,
    Pbkdf2Sha256PasswordHashingBackend,
    RandomTokenFactory,
    TokenHashingBackend,
)
from .service import neutral_login_failure_response
from .session_tokens import IssuedSession, SessionTokenService, SessionTokenStore

ACTIVE_AUTH_STATUS = "active"
ACTIVE_RECORD_STATUS = "active"


class CredentialStore(Protocol):
    """Storage interface for credential records and actor memberships."""

    def get_user_by_email_normalized(self, email_normalized: str) -> AuthUserRecord | None:
        """Return one active-or-inactive user record for a normalized email."""

    def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        """Return one user record by canonical UUID string."""


@dataclass(slots=True)
class InMemoryCredentialStore:
    """Process-local credential store with canonical UUID actor identifiers."""

    users: Iterable[AuthUserRecord] = ()
    _by_id: dict[str, AuthUserRecord] = field(init=False, default_factory=dict)
    _by_email: dict[str, AuthUserRecord] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        for user in self.users:
            self.upsert_user(user)

    def upsert_user(self, user: AuthUserRecord) -> AuthUserRecord:
        canonical_user_id = canonical_uuid_text(user.id)
        normalized_email = normalize_email(user.email_normalized)
        memberships = tuple(canonical_membership(record) for record in user.memberships)
        canonical_user = AuthUserRecord(
            id=canonical_user_id,
            email_normalized=normalized_email,
            password_hash=user.password_hash,
            auth_status=user.auth_status,
            record_status=user.record_status,
            session_version=user.session_version,
            memberships=memberships,
        )
        self._by_id[canonical_user.id] = canonical_user
        self._by_email[canonical_user.email_normalized] = canonical_user
        return canonical_user

    def get_user_by_email_normalized(self, email_normalized: str) -> AuthUserRecord | None:
        return self._by_email.get(normalize_email(email_normalized))

    def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        try:
            canonical_user_id = canonical_uuid_text(user_id)
        except ValueError:
            return None
        return self._by_id.get(canonical_user_id)


@dataclass(frozen=True, slots=True)
class AuthLoginResult:
    """Login outcome that carries plaintext tokens only at the response boundary."""

    issued_session: IssuedSession | None = None
    actor: Actor | None = None
    neutral_response: NeutralPublicResponse | None = None

    @property
    def authenticated(self) -> bool:
        return self.issued_session is not None and self.actor is not None


@dataclass(slots=True)
class AuthSessionService:
    """Credential verification, session issuance, and token actor resolution."""

    credentials: CredentialStore | None = None
    sessions: SessionTokenStore | None = None
    password_hasher: PasswordHashingBackend | None = None
    token_hashing: TokenHashingBackend | None = None
    token_factory: RandomTokenFactory = field(default_factory=RandomTokenFactory)
    bearer_session_ttl: timedelta = timedelta(hours=12)
    pwa_session_ttl: timedelta = timedelta(hours=12)

    @property
    def configured(self) -> bool:
        return all(
            primitive is not None
            for primitive in (
                self.credentials,
                self.sessions,
                self.password_hasher,
                self.token_hashing,
            )
        )

    def login(
        self,
        request: LoginRequest,
        *,
        request_id: str | None = None,
    ) -> AuthLoginResult:
        if not self.configured:
            return self._neutral_login(request_id)

        assert self.credentials is not None
        assert self.password_hasher is not None
        user = self.credentials.get_user_by_email_normalized(request.email)
        if user is None or not user_is_active(user):
            return self._neutral_login(request_id)

        if not self.password_hasher.verify_password(request.password, user.password_hash):
            return self._neutral_login(request_id)

        token_service = self._token_service()
        match request.transport:
            case AuthTransport.ANDROID_BEARER:
                issued = token_service.issue_android_tokens(
                    user_id=user.id,
                    session_version=user.session_version,
                )
            case AuthTransport.PWA_COOKIE:
                issued = token_service.issue_pwa_cookie_session(
                    user_id=user.id,
                    session_version=user.session_version,
                )
            case _:
                return self._neutral_login(request_id)

        actor = actor_from_user_record(
            user,
            session_id=issued.storage_record.id,
            request_id=request_id,
        )
        return AuthLoginResult(issued_session=issued, actor=actor)

    def actor_for_bearer_token(
        self,
        token_plaintext: str | None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> Actor | None:
        record = self._session_record_for_token(token_plaintext)
        return self._actor_for_session_record(
            record,
            client_kind=AuthClientKind.ANDROID,
            request_id=request_id,
            now=now,
        )

    def actor_for_cookie_session(
        self,
        token_plaintext: str | None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> Actor | None:
        record = self._session_record_for_token(token_plaintext)
        return self._actor_for_session_record(
            record,
            client_kind=AuthClientKind.PWA,
            request_id=request_id,
            now=now,
        )

    def csrf_token_matches_cookie_session(
        self,
        *,
        session_token_plaintext: str | None,
        csrf_token_plaintext: str | None,
        now: datetime | None = None,
    ) -> bool:
        record = self._session_record_for_token(session_token_plaintext)
        if (
            record is None
            or record.client_kind != AuthClientKind.PWA
            or not session_record_is_active(record, now=now)
            or not csrf_token_plaintext
            or not record.csrf_token_hash
            or self.token_hashing is None
        ):
            return False

        try:
            return self.token_hashing.verify_token(
                csrf_token_plaintext,
                record.csrf_token_hash,
            )
        except ValueError:
            return False

    def _actor_for_session_record(
        self,
        record: SessionStorageRecord | None,
        *,
        client_kind: AuthClientKind,
        request_id: str | None,
        now: datetime | None = None,
    ) -> Actor | None:
        if (
            record is None
            or record.client_kind != client_kind
            or not session_record_is_active(record, now=now)
        ):
            return None

        assert self.credentials is not None
        user = self.credentials.get_user_by_id(record.user_id)
        if user is None or not user_is_active(user):
            return None
        if user.session_version != record.session_version:
            return None

        return actor_from_user_record(user, session_id=record.id, request_id=request_id)

    def revoke_bearer_token(self, token_plaintext: str | None) -> bool:
        return self._revoke_token_for_client_kind(
            token_plaintext,
            client_kind=AuthClientKind.ANDROID,
        )

    def revoke_cookie_session(self, token_plaintext: str | None) -> bool:
        return self._revoke_token_for_client_kind(
            token_plaintext,
            client_kind=AuthClientKind.PWA,
        )

    def _revoke_token_for_client_kind(
        self,
        token_plaintext: str | None,
        *,
        client_kind: AuthClientKind,
    ) -> bool:
        record = self._session_record_for_token(token_plaintext)
        if record is None or record.client_kind != client_kind or self.sessions is None:
            return False

        self.sessions.revoke_session(session_id=record.id, revoked_at=datetime.now(UTC))
        return True

    def _session_record_for_token(self, token_plaintext: str | None) -> SessionStorageRecord | None:
        if not token_plaintext or not self.configured:
            return None

        assert self.sessions is not None
        assert self.token_hashing is not None
        try:
            token_hash = self.token_hashing.hash_token(token_plaintext)
        except ValueError:
            return None

        return self.sessions.get_session_by_session_token_hash(session_token_hash=token_hash)

    def _token_service(self) -> SessionTokenService:
        assert self.sessions is not None
        assert self.token_hashing is not None
        return SessionTokenService(
            store=self.sessions,
            token_factory=self.token_factory,
            hashing_backend=self.token_hashing,
            pwa_session_ttl=self.pwa_session_ttl,
            android_refresh_ttl=self.bearer_session_ttl,
        )

    @staticmethod
    def _neutral_login(request_id: str | None) -> AuthLoginResult:
        return AuthLoginResult(
            neutral_response=neutral_login_failure_response(request_id=request_id)
        )


def user_is_active(user: AuthUserRecord) -> bool:
    return user.auth_status == ACTIVE_AUTH_STATUS and user.record_status == ACTIVE_RECORD_STATUS


def session_record_is_active(
    record: SessionStorageRecord,
    *,
    now: datetime | None = None,
) -> bool:
    current_time = now or datetime.now(UTC)
    return (
        record.status == TokenRecordStatus.ACTIVE
        and record.revoked_at is None
        and record.expires_at > current_time
    )


def actor_from_user_record(
    user: AuthUserRecord,
    *,
    session_id: str | None,
    request_id: str | None,
) -> Actor:
    canonical_user_id = canonical_uuid_text(user.id)
    memberships = tuple(
        Membership(
            user_id=canonical_user_id,
            household_id=canonical_uuid_text(record.household_id),
            status=MembershipStatus(record.status),
        )
        for record in user.memberships
        if canonical_uuid_text(record.user_id) == canonical_user_id
    )
    return Actor(
        user_id=canonical_user_id,
        memberships=memberships,
        session_id=session_id,
        request_id=request_id,
    )


@lru_cache
def get_auth_session_service() -> AuthSessionService:
    """Return DB-backed auth service when secrets are wired; otherwise default-deny."""

    settings = get_settings()
    if not settings.auth_token_hash_secret:
        return AuthSessionService()

    try:
        token_hashing = HmacSha256TokenHashingBackend(secret=settings.auth_token_hash_secret)
        password_hasher = Pbkdf2Sha256PasswordHashingBackend(
            iterations=settings.auth_password_pbkdf2_iterations,
        )
    except AuthSecurityConfigurationError:
        return AuthSessionService()

    session_factory = sync_session_factory_for_settings(settings)
    return AuthSessionService(
        credentials=SqlAlchemyCredentialStore(session_factory),
        sessions=SqlAlchemySessionTokenStore(session_factory),
        password_hasher=password_hasher,
        token_hashing=token_hashing,
        bearer_session_ttl=timedelta(seconds=settings.auth_bearer_session_ttl_seconds),
        pwa_session_ttl=timedelta(seconds=settings.auth_pwa_session_ttl_seconds),
    )
