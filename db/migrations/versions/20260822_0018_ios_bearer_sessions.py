"""Allow native iOS bearer sessions.

Revision ID: 20260822_0018
Revises: 20260618_0017
Create Date: 2026-08-22

Rollback notes:
- Downgrade revokes compatibility by deleting iOS-only session rows before
  restoring the previous transport constraint.
- User credentials and all financial data are preserved.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0018"
down_revision: str | None = "20260618_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PREVIOUS_TRANSPORT_CHECK = "transport IN ('cookie', 'android_bearer')"
IOS_TRANSPORT_CHECK = "transport IN ('cookie', 'android_bearer', 'ios_bearer')"
TRANSPORT_CONSTRAINT_NAME = "ck_sessions_transport_valid"


def upgrade() -> None:
    _replace_transport_constraint(IOS_TRANSPORT_CHECK)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM sessions WHERE transport = 'ios_bearer'"))
    _replace_transport_constraint(PREVIOUS_TRANSPORT_CHECK)


def _replace_transport_constraint(check_sql: str) -> None:
    with op.batch_alter_table("sessions", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f(TRANSPORT_CONSTRAINT_NAME), type_="check")
        batch_op.create_check_constraint(op.f(TRANSPORT_CONSTRAINT_NAME), check_sql)
