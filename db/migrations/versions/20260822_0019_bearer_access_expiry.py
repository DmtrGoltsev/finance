"""Separate mobile access expiry from refresh/session expiry.

Revision ID: 20260822_0019
Revises: 20260822_0018
Create Date: 2026-08-22

Existing mobile sessions retain their former effective expiry for both token
classes. Newly issued and rotated sessions receive independent lifetimes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0019"
down_revision: str | None = "20260822_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE sessions SET access_expires_at = expires_at "
            "WHERE transport IN ('android_bearer', 'ios_bearer')"
        )
    )


def downgrade() -> None:
    op.drop_column("sessions", "access_expires_at")
