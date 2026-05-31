"""Create hash-only category aggregate mapping table.

Revision ID: 20260531_0009
Revises: 20260528_0008
Create Date: 2026-05-31

Rollback notes:
- Downgrade drops only capture_category_mappings and its indexes.
- No raw external label, OCR text, or screenshot image columns are created.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260531_0009"
down_revision: str | None = "20260528_0008"
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
        "capture_category_mappings",
        *_base_columns(),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("category_id", UUID, nullable=False),
        sa.Column("external_label_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(external_label_hash) = 64",
            name=op.f("ck_capture_category_mappings_external_label_hash_sha256"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_capture_category_mappings_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_capture_category_mappings_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_capture_category_mappings_category_id_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capture_category_mappings")),
    )
    op.create_index(
        "uq_capture_category_mappings_owner_personal_hash",
        "capture_category_mappings",
        ["owner_user_id", "external_label_hash"],
        unique=True,
        postgresql_where=sa.text("household_id IS NULL"),
    )
    op.create_index(
        "uq_capture_category_mappings_owner_household_hash",
        "capture_category_mappings",
        ["owner_user_id", "household_id", "external_label_hash"],
        unique=True,
        postgresql_where=sa.text("household_id IS NOT NULL"),
    )
    op.create_index(
        "ix_capture_category_mappings_category_id",
        "capture_category_mappings",
        ["category_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capture_category_mappings_category_id",
        table_name="capture_category_mappings",
    )
    op.drop_index(
        "uq_capture_category_mappings_owner_household_hash",
        table_name="capture_category_mappings",
    )
    op.drop_index(
        "uq_capture_category_mappings_owner_personal_hash",
        table_name="capture_category_mappings",
    )
    op.drop_table("capture_category_mappings")
