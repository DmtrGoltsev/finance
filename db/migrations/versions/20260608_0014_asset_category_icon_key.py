"""Add nullable icon key to asset categories.

Revision ID: 20260608_0014
Revises: 20260607_0013
Create Date: 2026-06-08

Rollback notes:
- Downgrade drops only the additive nullable asset category icon metadata.
- Existing asset category records remain otherwise unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260608_0014"
down_revision: str | None = "20260607_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("asset_categories") as batch_op:
        batch_op.add_column(sa.Column("icon_key", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("asset_categories") as batch_op:
        batch_op.drop_column("icon_key")
