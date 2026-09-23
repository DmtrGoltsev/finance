"""Add the server-verified MOEX identifier catalog."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0022"
down_revision: str | None = "20260919_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "moex_instruments",
        sa.Column("secid", sa.Text(), primary_key=True),
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_moex_instruments_isin", "moex_instruments", ["isin"])


def downgrade() -> None:
    op.drop_index("ix_moex_instruments_isin", table_name="moex_instruments")
    op.drop_table("moex_instruments")
