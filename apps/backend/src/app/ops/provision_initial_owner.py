"""Provision a minimal production QA owner without loading dev seed data."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
import sys
from uuid import UUID, uuid4

from sqlalchemy import select

from app.auth.identifiers import normalize_email
from app.auth.security import Pbkdf2Sha256PasswordHashingBackend
from app.config import Settings, get_settings
from app.db.models import Household, Membership, Session, User
from app.db.session import (
    is_production_like_environment,
    sync_session_factory_for_settings,
    validate_database_runtime_policy,
)

PASSWORD_ENV_NAME = "FINANCE_BACKEND_PROVISION_PASSWORD"
ROTATE_REASON = "provision_password_rotation"


class ProvisioningError(RuntimeError):
    """Raised when provisioning is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class ProvisionInitialOwnerResult:
    user_id: str
    email_normalized: str
    user_created: bool
    password_rotated: bool
    household_id: str | None
    household_created: bool
    membership_id: str | None
    membership_created: bool
    active_sessions_revoked: int


def provision_initial_owner(
    *,
    settings: Settings,
    email: str,
    password: str | None,
    display_name: str,
    household_name: str,
    rotate_password: bool = False,
    confirm_production: bool = False,
    now: datetime | None = None,
) -> ProvisionInitialOwnerResult:
    """Create or verify the first QA owner with an active household membership.

    The command intentionally inserts only auth bootstrap rows. It does not create
    accounts, categories, transactions, reports, imports, or sessions.
    """

    _validate_runtime_guards(settings, confirm_production=confirm_production)

    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ProvisioningError("email is required")

    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    session_factory = sync_session_factory_for_settings(settings)
    password_hasher = Pbkdf2Sha256PasswordHashingBackend(
        iterations=settings.auth_password_pbkdf2_iterations,
    )

    with session_factory.begin() as session:
        user = session.execute(
            select(User).where(
                User.email_normalized == normalized_email,
                User.record_status != "deleted",
            )
        ).scalar_one_or_none()

        user_created = user is None
        password_rotated = False
        revoked_sessions = 0

        if user is None:
            _require_password(password)
            user = User(
                id=uuid4(),
                email_normalized=normalized_email,
                password_hash=password_hasher.hash_password(password or ""),
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
        else:
            if user.record_status == "deleted":
                raise ProvisioningError("refusing to provision a deleted user")
            if user.auth_status != "active":
                raise ProvisioningError("refusing to reactivate an inactive user")
            if rotate_password:
                _require_password(password)
                user.password_hash = password_hasher.hash_password(password or "")
                user.session_version = int(user.session_version or 1) + 1
                user.updated_at = current_time
                password_rotated = True
                revoked_sessions = _revoke_active_sessions(session, user.id, current_time)

        active_membership = session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.membership_status == "active",
            )
        ).scalar_one_or_none()

        household_created = False
        membership_created = False
        household_id: UUID | None = None
        membership_id: UUID | None = None

        if active_membership is None:
            household = Household(
                id=uuid4(),
                name=household_name,
                created_by_user_id=user.id,
                status="active",
                record_status="active",
                membership_version=1,
                created_at=current_time,
                updated_at=current_time,
                version=1,
            )
            session.add(household)
            session.flush()
            household_created = True
            household_id = household.id

            active_membership = Membership(
                id=uuid4(),
                household_id=household.id,
                user_id=user.id,
                membership_status="active",
                invited_by_user_id=None,
                invited_at=None,
                joined_at=current_time,
                ended_at=None,
                created_at=current_time,
                updated_at=current_time,
                version=1,
            )
            session.add(active_membership)
            session.flush()
            membership_created = True
            membership_id = active_membership.id
        else:
            household_id = active_membership.household_id
            membership_id = active_membership.id

        return ProvisionInitialOwnerResult(
            user_id=str(user.id),
            email_normalized=normalized_email,
            user_created=user_created,
            password_rotated=password_rotated,
            household_id=str(household_id) if household_id else None,
            household_created=household_created,
            membership_id=str(membership_id) if membership_id else None,
            membership_created=membership_created,
            active_sessions_revoked=revoked_sessions,
        )


def _validate_runtime_guards(settings: Settings, *, confirm_production: bool) -> None:
    if is_production_like_environment(settings.environment):
        if not confirm_production:
            raise ProvisioningError("production-like provisioning requires --confirm-production")
        validate_database_runtime_policy(settings, repository_mode="db")
        if not settings.auth_token_hash_secret:
            raise ProvisioningError("FINANCE_BACKEND_AUTH_TOKEN_HASH_SECRET is required")


def _require_password(password: str | None) -> None:
    if not password:
        raise ProvisioningError(f"{PASSWORD_ENV_NAME} is required for create/rotate")
    if len(password) < 12:
        raise ProvisioningError(f"{PASSWORD_ENV_NAME} must be at least 12 characters")


def _revoke_active_sessions(session, user_id: UUID, revoked_at: datetime) -> int:
    rows = session.execute(
        select(Session).where(Session.user_id == user_id, Session.status == "active")
    ).scalars()
    count = 0
    for row in rows:
        row.status = "revoked"
        row.revoked_at = revoked_at
        row.revoked_reason = ROTATE_REASON
        row.updated_at = revoked_at
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", default="Finance QA Owner")
    parser.add_argument("--household-name", default="Finance QA Household")
    parser.add_argument("--rotate-password", action="store_true")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = provision_initial_owner(
            settings=get_settings(),
            email=args.email,
            password=os.environ.get(PASSWORD_ENV_NAME),
            display_name=args.display_name,
            household_name=args.household_name,
            rotate_password=args.rotate_password,
            confirm_production=args.confirm_production,
        )
    except ProvisioningError as exc:
        print(f"provisioning failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
