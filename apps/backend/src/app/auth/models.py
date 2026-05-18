"""Storage-facing auth model skeletons.

These are not SQLAlchemy models yet. They document the fields that future DB
models must persist once storage ownership lands. Plaintext session, reset,
invite, and refresh tokens are never represented here; only approved hashes are
storage-facing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AuthClientKind(StrEnum):
    PWA = "pwa"
    ANDROID = "android"


class SessionTokenKind(StrEnum):
    PWA_COOKIE_SESSION = "pwa_cookie_session"
    ANDROID_ACCESS = "android_access"
    ANDROID_REFRESH = "android_refresh"


class TokenRecordStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class AuthMembershipRecord:
    user_id: str
    household_id: str
    status: str


@dataclass(frozen=True, slots=True)
class AuthUserRecord:
    id: str
    email_normalized: str
    password_hash: str
    auth_status: str = "active"
    record_status: str = "active"
    session_version: int = 1
    memberships: tuple[AuthMembershipRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionStorageRecord:
    id: str
    user_id: str
    client_kind: AuthClientKind
    session_version: int
    issued_at: datetime
    expires_at: datetime
    status: TokenRecordStatus = TokenRecordStatus.ACTIVE
    session_token_hash: str | None = None
    refresh_token_hash: str | None = None
    csrf_token_hash: str | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PasswordResetTokenStorageRecord:
    id: str
    user_id: str
    reset_token_hash: str
    requested_email_hash: str
    issued_at: datetime
    expires_at: datetime
    status: TokenRecordStatus = TokenRecordStatus.ACTIVE
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class InviteTokenStorageRecord:
    id: str
    invite_id: str
    household_id: str
    invite_token_hash: str
    issued_by_user_id: str
    issued_at: datetime
    expires_at: datetime
    status: TokenRecordStatus = TokenRecordStatus.ACTIVE
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None
