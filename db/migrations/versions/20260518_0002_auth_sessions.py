"""Create DB-backed auth sessions table.

Revision ID: 20260518_0002
Revises: 20260517_0001
Create Date: 2026-05-18

Rollback notes:
- Downgrade drops only revocable session rows and their indexes.
- User, household, membership, account, and category data from the first slice
  is preserved.
- Prefer forward fixes after real session data exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260518_0002"
down_revision: str | None = "20260517_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
    ]


def upgrade() -> None:
    op.create_table(
        "sessions",
        *_base_columns(),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("session_token_hash", sa.Text(), nullable=True),
        sa.Column("refresh_token_hash", sa.Text(), nullable=True),
        sa.Column("transport", sa.Text(), nullable=False),
        sa.Column("session_version", sa.BigInteger(), nullable=False),
        sa.Column("csrf_token_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "transport IN ('cookie', 'android_bearer')",
            name=op.f("ck_sessions_transport_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name=op.f("ck_sessions_status_valid"),
        ),
        sa.CheckConstraint(
            "session_token_hash IS NOT NULL OR refresh_token_hash IS NOT NULL",
            name=op.f("ck_sessions_at_least_one_token_hash"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_sessions_session_token_hash")),
        sa.UniqueConstraint("refresh_token_hash", name=op.f("uq_sessions_refresh_token_hash")),
    )
    op.create_index(
        "ix_sessions_user_active_expires",
        "sessions",
        ["user_id", "status", "expires_at"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_sessions_session_version", "sessions", ["session_version"])


def downgrade() -> None:
    op.drop_index("ix_sessions_session_version", table_name="sessions")
    op.drop_index("ix_sessions_user_active_expires", table_name="sessions")
    op.drop_table("sessions")
