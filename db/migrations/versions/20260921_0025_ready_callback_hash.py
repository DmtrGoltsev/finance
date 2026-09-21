"""Persist the accepted ready callback identity for immutable replay checks."""

import sqlalchemy as sa
from alembic import op

revision = "20260921_0025"
down_revision = "20260920_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("recommendation_reports", sa.Column("callback_hash", sa.Text()))


def downgrade():
    op.drop_column("recommendation_reports", "callback_hash")
