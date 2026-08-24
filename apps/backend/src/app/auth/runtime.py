"""Mounted auth/session runtime for the MVP bearer-token foundation."""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Protocol
from uuid import uuid4

from app.authz import Actor, Membership, MembershipStatus
from app.config import get_settings
from app.db.session import sync_session_factory_for_settings

from .db_stores import (
    DuplicateUserEmailError,
    SqlAlchemyCredentialStore,
    SqlAlchemySessionTokenStore,
)
from .identifiers import canonical_membership, canonical_uuid_text, normalize_email
from .models import AuthClientKind, AuthUserRecord, SessionStorageRecord, TokenRecordStatus
from .schemas import AuthTransport, LoginRequest, NeutralPublicResponse, RegistrationRequest
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
BEARER_CLIENT_KIND_BY_TRANSPORT = {
    AuthTransport.ANDROID_BEARER: AuthClientKind.ANDROID,
    AuthTransport.IOS_BEARER: AuthClientKind.IOS,
}
BEARER_CLIENT_KINDS = frozenset(BEARER_CLIENT_KIND_BY_TRANSPORT.values())


class CredentialStore(Protocol):
    """Storage interface for credential records and actor memberships."""

    def create_user(
        self,
        *,
        email_normalized: str,
        password_hash: str,
        display_name: str | None,
        created_at: datetime,
    ) -> AuthUserRecord:
        """Create an active user with a pre-hashed password."""

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

    def create_user(
        self,
        *,
        email_normalized: str,
        password_hash: str,
        display_name: str | None,
        created_at: datetime,
    ) -> AuthUserRecord:
        del display_name, created_at
        normalized_email = normalize_email(email_normalized)
        if normalized_email in self._by_email:
            raise DuplicateUserEmailError("registration email is already in use")

        return self.upsert_user(
            AuthUserRecord(
                id=canonical_uuid_text(uuid4()),
                email_normalized=normalized_email,
                password_hash=password_hash,
                auth_status=ACTIVE_AUTH_STATUS,
                record_status=ACTIVE_RECORD_STATUS,
                session_version=1,
                memberships=(),
            )
        )

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


@dataclass(frozen=True, slots=True)
class AuthRegistrationResult:
    """Registration outcome that carries plaintext tokens only at the response boundary."""

    issued_session: IssuedSession | None = None
    actor: Actor | None = None
    conflict: bool = False
    unavailable: bool = False

    @property
    def registered(self) -> bool:
        return self.issued_session is not None and self.actor is not None


@dataclass(frozen=True, slots=True)
class AuthRefreshResult:
    """Refresh outcome that carries rotated plaintext tokens only at the response boundary."""

    issued_session: IssuedSession | None = None
    actor: Actor | None = None

    @property
    def refreshed(self) -> bool:
        return self.issued_session is not None and self.actor is not None


@dataclass(slots=True)
class AuthSessionService:
    """Credential verification, session issuance, and token actor resolution."""

    credentials: CredentialStore | None = None
    sessions: SessionTokenStore | None = None
    password_hasher: PasswordHashingBackend | None = None
    token_hashing: TokenHashingBackend | None = None
    token_factory: RandomTokenFactory = field(default_factory=RandomTokenFactory)
    bearer_access_ttl: timedelta = timedelta(minutes=15)
    bearer_session_ttl: timedelta = timedelta(days=30)
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
            case AuthTransport.ANDROID_BEARER | AuthTransport.IOS_BEARER:
                issued = token_service.issue_bearer_tokens(
                    user_id=user.id,
                    client_kind=BEARER_CLIENT_KIND_BY_TRANSPORT[request.transport],
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

    def register(
        self,
        request: RegistrationRequest,
        *,
        request_id: str | None = None,
    ) -> AuthRegistrationResult:
        if not self.configured:
            return AuthRegistrationResult(unavailable=True)

        assert self.credentials is not None
        assert self.password_hasher is not None
        try:
            user = self.credentials.create_user(
                email_normalized=normalize_email(request.email),
                password_hash=self.password_hasher.hash_password(request.password),
                display_name=request.display_name,
                created_at=datetime.now(UTC),
            )
        except DuplicateUserEmailError:
            return AuthRegistrationResult(conflict=True)

        token_service = self._token_service()
        match request.transport:
            case AuthTransport.ANDROID_BEARER | AuthTransport.IOS_BEARER:
                issued = token_service.issue_bearer_tokens(
                    user_id=user.id,
                    client_kind=BEARER_CLIENT_KIND_BY_TRANSPORT[request.transport],
                    session_version=user.session_version,
                )
            case AuthTransport.PWA_COOKIE:
                issued = token_service.issue_pwa_cookie_session(
                    user_id=user.id,
                    session_version=user.session_version,
                )
            case _:
                return AuthRegistrationResult(unavailable=True)

        actor = actor_from_user_record(
            user,
            session_id=issued.storage_record.id,
            request_id=request_id,
        )
        return AuthRegistrationResult(issued_session=issued, actor=actor)

    def actor_for_bearer_token(
        self,
        token_plaintext: str | None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> Actor | None:
        record = self._session_record_for_token(token_plaintext)
        if record is None or record.client_kind not in BEARER_CLIENT_KINDS:
            return None
        return self._actor_for_session_record(
            record,
            client_kind=record.client_kind,
            request_id=request_id,
            now=now,
            require_active_access=True,
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

    def refresh_android_session(
        self,
        refresh_token_plaintext: str | None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthRefreshResult:
        """Refresh only an Android session for backward-compatible internal callers."""

        return self._refresh_bearer_session(
            refresh_token_plaintext,
            required_client_kind=AuthClientKind.ANDROID,
            request_id=request_id,
            now=now,
        )

    def refresh_bearer_session(
        self,
        refresh_token_plaintext: str | None,
        *,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthRefreshResult:
        """Refresh an Android or iOS bearer session, inferred from the stored token hash."""

        return self._refresh_bearer_session(
            refresh_token_plaintext,
            request_id=request_id,
            now=now,
        )

    def _refresh_bearer_session(
        self,
        refresh_token_plaintext: str | None,
        *,
        required_client_kind: AuthClientKind | None = None,
        request_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthRefreshResult:
        record = self._session_record_for_refresh_token(refresh_token_plaintext)
        if (
            record is None
            or record.client_kind not in BEARER_CLIENT_KINDS
            or (required_client_kind is not None and record.client_kind != required_client_kind)
        ):
            return AuthRefreshResult()
        actor = self._actor_for_session_record(
            record,
            client_kind=record.client_kind,
            request_id=request_id,
            now=now,
        )
        if (
            record is None
            or actor is None
            or record.refresh_token_hash is None
            or self.sessions is None
        ):
            return AuthRefreshResult()

        issued = self._token_service().rotate_bearer_tokens(
            record=record,
            old_refresh_token_hash=record.refresh_token_hash,
            rotated_at=now,
        )
        if issued is None:
            return AuthRefreshResult()

        return AuthRefreshResult(issued_session=issued, actor=actor)

    def _actor_for_session_record(
        self,
        record: SessionStorageRecord | None,
        *,
        client_kind: AuthClientKind,
        request_id: str | None,
        now: datetime | None = None,
        require_active_access: bool = False,
    ) -> Actor | None:
        if (
            record is None
            or record.client_kind != client_kind
            or not session_record_is_active(record, now=now)
            or (require_active_access and not bearer_access_record_is_active(record, now=now))
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
        record = self._session_record_for_token(token_plaintext)
        if record is None or record.client_kind not in BEARER_CLIENT_KINDS or self.sessions is None:
            return False

        self.sessions.revoke_session(session_id=record.id, revoked_at=datetime.now(UTC))
        return True

    def bearer_revoke_token(self, session_id: str) -> str:
        if not session_id or self.token_hashing is None:
            return ""
        return self.token_hashing.hash_token(f"session-revoke:{session_id}")

    def revoke_bearer_session(self, *, session_id: str, revoke_token: str) -> bool:
        if (
            self.sessions is None
            or self.token_hashing is None
            or not session_id
            or not revoke_token
        ):
            return False
        expected = self.bearer_revoke_token(session_id)
        if not expected or not hmac.compare_digest(expected, revoke_token):
            return False
        self.sessions.revoke_session(session_id=session_id, revoked_at=datetime.now(UTC))
        return True

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

    def _session_record_for_refresh_token(
        self,
        refresh_token_plaintext: str | None,
    ) -> SessionStorageRecord | None:
        if not refresh_token_plaintext or not self.configured:
            return None

        assert self.sessions is not None
        assert self.token_hashing is not None
        try:
            token_hash = self.token_hashing.hash_token(refresh_token_plaintext)
        except ValueError:
            return None

        return self.sessions.get_session_by_refresh_token_hash(refresh_token_hash=token_hash)

    def _token_service(self) -> SessionTokenService:
        assert self.sessions is not None
        assert self.token_hashing is not None
        return SessionTokenService(
            store=self.sessions,
            token_factory=self.token_factory,
            hashing_backend=self.token_hashing,
            pwa_session_ttl=self.pwa_session_ttl,
            bearer_access_ttl=self.bearer_access_ttl,
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


def bearer_access_record_is_active(
    record: SessionStorageRecord,
    *,
    now: datetime | None = None,
) -> bool:
    if record.client_kind not in BEARER_CLIENT_KINDS or record.access_expires_at is None:
        return False
    current_time = now or datetime.now(UTC)
    return record.access_expires_at > current_time


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
        bearer_access_ttl=timedelta(seconds=settings.auth_bearer_access_ttl_seconds),
        bearer_session_ttl=timedelta(seconds=settings.effective_auth_bearer_refresh_ttl_seconds),
        pwa_session_ttl=timedelta(seconds=settings.auth_pwa_session_ttl_seconds),
    )
