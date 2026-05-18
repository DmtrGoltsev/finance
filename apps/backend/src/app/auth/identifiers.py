"""Canonical auth identity helpers shared by runtime and DB adapters."""

from __future__ import annotations

from uuid import UUID

from app.authz import MembershipStatus

from .models import AuthMembershipRecord


def normalize_email(email: str) -> str:
    return email.strip().lower()


def canonical_uuid_text(value: str | UUID) -> str:
    return str(UUID(str(value)))


def canonical_membership(record: AuthMembershipRecord) -> AuthMembershipRecord:
    user_id = canonical_uuid_text(record.user_id)
    household_id = canonical_uuid_text(record.household_id)
    status = MembershipStatus(record.status)
    return AuthMembershipRecord(
        user_id=user_id,
        household_id=household_id,
        status=status.value,
    )
