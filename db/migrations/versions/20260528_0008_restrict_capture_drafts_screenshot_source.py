"""Restrict capture draft sources to screenshot OCR only.

Revision ID: 20260528_0008
Revises: 20260523_0007
Create Date: 2026-05-28

Upgrade notes:
- This migration is non-destructive.
- If legacy capture drafts with removed sources exist, upgrade stops and does not
  delete or rewrite production data.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0008"
down_revision: str | None = "20260523_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT_NAME = "ck_capture_drafts_capture_source_valid"
LEGACY_SOURCE_COUNT_SQL = sa.text(
    "SELECT count(*) FROM capture_drafts WHERE capture_source <> 'screenshot'"
)


def upgrade() -> None:
    legacy_count = op.get_bind().execute(LEGACY_SOURCE_COUNT_SQL).scalar_one()
    if legacy_count:
        raise RuntimeError(
            "capture_drafts contains removed capture_source values; "
            "manual data decision required before tightening the CHECK constraint"
        )

    op.drop_constraint(op.f(CONSTRAINT_NAME), "capture_drafts", type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        "capture_drafts",
        "capture_source IN ('screenshot')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT_NAME), "capture_drafts", type_="check")
    op.create_check_constraint(
        op.f(CONSTRAINT_NAME),
        "capture_drafts",
        "capture_source IN ('sms', 'notification', 'screenshot')",
    )
