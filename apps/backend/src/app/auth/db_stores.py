"""SQLAlchemy-backed auth credential and session stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Membership as MembershipModel
from app.db.models import Session as SessionModel
from app.db.models import User as UserModel

from .identifiers import canonical_uuid_text, normalize_email
from .models import (
    AuthClientKind,
    AuthMembershipRecord,
    AuthUserRecord,
    SessionStorageRecord,
    TokenRecordStatus,
)
from .security import TOKEN_HASH_PREFIX

SESSION_TRANSPORT_BY_CLIENT_KIND = {
    AuthClientKind.PWA: "cookie",
    AuthClientKind.ANDROID: "android_bearer",
    AuthClientKind.IOS: "ios_bearer",
}
CLIENT_KIND_BY_SESSION_TRANSPORT = {
    value: key for key, value in SESSION_TRANSPORT_BY_CLIENT_KIND.items()
}


class DuplicateUserEmailError(ValueError):
    """Raised when an active/non-deleted user already owns the registration email."""


@dataclass(slots=True)
class SqlAlchemyCredentialStore:
    """Credential store backed by ``users`` and ``memberships`` tables."""

    session_factory: sessionmaker[OrmSession]

    def create_user(
        self,
        *,
        email_normalized: str,
        password_hash: str,
        display_name: str | None,
        created_at: datetime,
    ) -> AuthUserRecord:
        normalized_email = normalize_email(email_normalized)
        current_time = _aware_utc(created_at)

        try:
            with self.session_factory.begin() as session:
                existing = session.execute(
                    select(UserModel).where(
                        UserModel.email_normalized == normalized_email,
                        UserModel.record_status != "deleted",
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    raise DuplicateUserEmailError("registration email is already in use")

                user = UserModel(
                    id=uuid4(),
                    email_normalized=normalized_email,
                    password_hash=password_hash,
                    display_name=display_name,
                    auth_status="active",
                    record_status="active",
                    session_version=1,
                    created_at=current_time,
                    updated_at=current_time,
                    version=1,
                )
                session.add(user)
                session.flush()
                return _user_record_from_model(session, user)
        except IntegrityError as exc:
            raise DuplicateUserEmailError("registration email is already in use") from exc

    def get_user_by_email_normalized(self, email_normalized: str) -> AuthUserRecord | None:
        normalized_email = normalize_email(email_normalized)
        with self.session_factory() as session:
            user = session.execute(
                select(UserModel).where(
                    UserModel.email_normalized == normalized_email,
                    UserModel.record_status != "deleted",
                )
            ).scalar_one_or_none()
            if user is None:
                return None
            return _user_record_from_model(session, user)

    def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        try:
            canonical_user_id = UUID(canonical_uuid_text(user_id))
        except ValueError:
            return None

        with self.session_factory() as session:
            user = session.get(UserModel, canonical_user_id)
            if user is None:
                return None
            return _user_record_from_model(session, user)


@dataclass(slots=True)
class SqlAlchemySessionTokenStore:
    """Hash-only session store backed by the ``sessions`` table."""

    session_factory: sessionmaker[OrmSession]

    def store_session(self, record: SessionStorageRecord) -> SessionStorageRecord:
        _validate_hash_only_record(record)
        issued_at = _aware_utc(record.issued_at)
        with self.session_factory.begin() as session:
            model = SessionModel(
                id=UUID(canonical_uuid_text(record.id)),
                user_id=UUID(canonical_uuid_text(record.user_id)),
                session_token_hash=record.session_token_hash,
                refresh_token_hash=record.refresh_token_hash,
                transport=_transport_from_client_kind(record.client_kind),
                session_version=int(record.session_version),
                csrf_token_hash=record.csrf_token_hash,
                status=record.status.value,
                last_seen_at=None,
                access_expires_at=_optional_aware_utc(record.access_expires_at),
                expires_at=_aware_utc(record.expires_at),
                revoked_at=_optional_aware_utc(record.revoked_at),
                revoked_reason=None,
                created_at=issued_at,
                updated_at=issued_at,
                version=1,
            )
            session.add(model)
            session.flush()
            return _session_record_from_model(model)

    def get_session_by_session_token_hash(
        self,
        *,
        session_token_hash: str,
    ) -> SessionStorageRecord | None:
        if not _is_approved_token_hash(session_token_hash):
            return None

        with self.session_factory() as session:
            model = session.execute(
                select(SessionModel).where(
                    SessionModel.session_token_hash == session_token_hash
                )
            ).scalar_one_or_none()
            if model is None:
                return None
            return _session_record_from_model(model)

    def get_session_by_refresh_token_hash(
        self,
        *,
        refresh_token_hash: str,
    ) -> SessionStorageRecord | None:
        if not _is_approved_token_hash(refresh_token_hash):
            return None

        with self.session_factory() as session:
            model = session.execute(
                select(SessionModel).where(SessionModel.refresh_token_hash == refresh_token_hash)
            ).scalar_one_or_none()
            if model is None:
                return None
            return _session_record_from_model(model)

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
        parsed_session_id = _optional_uuid(session_id)
        if (
            parsed_session_id is None
            or client_kind not in (AuthClientKind.ANDROID, AuthClientKind.IOS)
            or not _is_approved_token_hash(old_refresh_token_hash)
            or not _is_approved_token_hash(new_session_token_hash)
            or not _is_approved_token_hash(new_refresh_token_hash)
        ):
            return None

        rotated_at_utc = _aware_utc(rotated_at)
        new_access_expires_at_utc = (
            _aware_utc(new_access_expires_at) if new_access_expires_at is not None else None
        )
        new_expires_at_utc = _aware_utc(new_expires_at) if new_expires_at is not None else None
        updated_values = {
            "session_token_hash": new_session_token_hash,
            "refresh_token_hash": new_refresh_token_hash,
            "last_seen_at": rotated_at_utc,
            "updated_at": rotated_at_utc,
        }
        if new_expires_at_utc is not None:
            updated_values["expires_at"] = new_expires_at_utc
        if new_access_expires_at_utc is not None:
            updated_values["access_expires_at"] = new_access_expires_at_utc
        with self.session_factory.begin() as session:
            result = session.execute(
                update(SessionModel)
                .where(
                    SessionModel.id == parsed_session_id,
                    SessionModel.refresh_token_hash == old_refresh_token_hash,
                    SessionModel.transport == SESSION_TRANSPORT_BY_CLIENT_KIND[client_kind],
                    SessionModel.status == TokenRecordStatus.ACTIVE.value,
                    SessionModel.revoked_at.is_(None),
                    SessionModel.expires_at > rotated_at_utc,
                )
                .values(**updated_values)
            )
            if result.rowcount != 1:
                return None

            model = session.execute(
                select(SessionModel).where(SessionModel.id == parsed_session_id)
            ).scalar_one()
            return _session_record_from_model(model)

    def rotate_android_session_tokens(
        self,
        *,
        session_id: str,
        old_refresh_token_hash: str,
        new_session_token_hash: str,
        new_refresh_token_hash: str,
        rotated_at: datetime,
        new_access_expires_at: datetime | None = None,
        new_expires_at: datetime | None = None,
    ) -> SessionStorageRecord | None:
        """Backward-compatible wrapper retained for existing Android callers."""

        return self.rotate_bearer_session_tokens(
            session_id=session_id,
            client_kind=AuthClientKind.ANDROID,
            old_refresh_token_hash=old_refresh_token_hash,
            new_session_token_hash=new_session_token_hash,
            new_refresh_token_hash=new_refresh_token_hash,
            rotated_at=rotated_at,
            new_access_expires_at=new_access_expires_at,
            new_expires_at=new_expires_at,
        )

    def revoke_session(self, *, session_id: str, revoked_at: datetime) -> None:
        parsed_session_id = _optional_uuid(session_id)
        if parsed_session_id is None:
            return

        with self.session_factory.begin() as session:
            model = session.get(SessionModel, parsed_session_id)
            if model is None:
                return
            model.status = TokenRecordStatus.REVOKED.value
            model.revoked_at = _aware_utc(revoked_at)
            model.updated_at = _aware_utc(revoked_at)

    def revoke_user_sessions(self, *, user_id: str, revoked_at: datetime) -> None:
        parsed_user_id = _optional_uuid(user_id)
        if parsed_user_id is None:
            return

        revoked_at_utc = _aware_utc(revoked_at)
        with self.session_factory.begin() as session:
            rows = session.execute(
                select(SessionModel).where(
                    SessionModel.user_id == parsed_user_id,
                    SessionModel.status == TokenRecordStatus.ACTIVE.value,
                )
            ).scalars()
            for model in rows:
                model.status = TokenRecordStatus.REVOKED.value
                model.revoked_at = revoked_at_utc
                model.updated_at = revoked_at_utc

    def records_for_tests(self) -> tuple[SessionStorageRecord, ...]:
        with self.session_factory() as session:
            rows = session.execute(select(SessionModel)).scalars().all()
            return tuple(_session_record_from_model(row) for row in rows)


def _user_record_from_model(session: OrmSession, user: UserModel) -> AuthUserRecord:
    memberships = session.execute(
        select(MembershipModel).where(MembershipModel.user_id == user.id)
    ).scalars()
    return AuthUserRecord(
        id=canonical_uuid_text(user.id),
        email_normalized=normalize_email(user.email_normalized or ""),
        password_hash=user.password_hash,
        auth_status=user.auth_status,
        record_status=user.record_status,
        session_version=int(user.session_version or 1),
        memberships=tuple(
            AuthMembershipRecord(
                user_id=canonical_uuid_text(membership.user_id),
                household_id=canonical_uuid_text(membership.household_id),
                status=membership.membership_status,
            )
            for membership in memberships
        ),
    )


def _session_record_from_model(model: SessionModel) -> SessionStorageRecord:
    return SessionStorageRecord(
        id=canonical_uuid_text(model.id),
        user_id=canonical_uuid_text(model.user_id),
        client_kind=_client_kind_from_transport(model.transport),
        session_version=int(model.session_version),
        issued_at=_aware_utc(model.created_at),
        expires_at=_aware_utc(model.expires_at),
        access_expires_at=_optional_aware_utc(model.access_expires_at),
        status=TokenRecordStatus(model.status),
        session_token_hash=model.session_token_hash,
        refresh_token_hash=model.refresh_token_hash,
        csrf_token_hash=model.csrf_token_hash,
        revoked_at=_optional_aware_utc(model.revoked_at),
    )


def _validate_hash_only_record(record: SessionStorageRecord) -> None:
    if record.session_token_hash is None and record.refresh_token_hash is None:
        raise ValueError("session storage requires at least one approved token hash")

    for field_name, token_hash in (
        ("session_token_hash", record.session_token_hash),
        ("refresh_token_hash", record.refresh_token_hash),
        ("csrf_token_hash", record.csrf_token_hash),
    ):
        if token_hash is not None and not _is_approved_token_hash(token_hash):
            raise ValueError(f"{field_name} must contain an approved auth token hash")


def _is_approved_token_hash(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(TOKEN_HASH_PREFIX)


def _transport_from_client_kind(client_kind: AuthClientKind) -> str:
    try:
        return SESSION_TRANSPORT_BY_CLIENT_KIND[client_kind]
    except KeyError as exc:
        raise ValueError(f"unsupported auth client kind: {client_kind!r}") from exc


def _client_kind_from_transport(transport: str) -> AuthClientKind:
    try:
        return CLIENT_KIND_BY_SESSION_TRANSPORT[transport]
    except KeyError as exc:
        raise ValueError(f"unsupported session transport: {transport!r}") from exc


def _optional_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _optional_aware_utc(value: datetime | None) -> datetime | None:
    return _aware_utc(value) if value is not None else None
