"""Add owner-scoped brokerage account profiles to portfolio imports and snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0023"
down_revision: str | None = "20260920_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "brokerage_account_profiles",
        sa.Column("id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=False),
        sa.Column("brokerage", sa.Text(), nullable=False),
        sa.Column("user_label", sa.Text(), nullable=False),
        sa.Column("label_key", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "brokerage IN ('sinara', 'sber_investments', 'finam')",
            name=op.f("ck_brokerage_account_profiles_brokerage_valid"),
        ),
        sa.CheckConstraint(
            "account_type IN ('brokerage', 'iis_a', 'iis_b', 'iis_iii')",
            name=op.f("ck_brokerage_account_profiles_account_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"],
            name=op.f("fk_brokerage_account_profiles_owner_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brokerage_account_profiles")),
        sa.UniqueConstraint(
            "owner_user_id", "brokerage", "label_key",
            name="uq_brokerage_account_profiles_owner_brokerage_label",
        ),
    )
    op.create_index(
        "ix_brokerage_account_profiles_owner_brokerage",
        "brokerage_account_profiles", ["owner_user_id", "brokerage"],
    )
    op.add_column("portfolio_imports", sa.Column("account_profile_id", UUID, nullable=True))
    op.create_foreign_key(
        op.f("fk_portfolio_imports_account_profile_id_brokerage_account_profiles"),
        "portfolio_imports", "brokerage_account_profiles",
        ["account_profile_id"], ["id"],
    )
    op.add_column("portfolio_snapshots", sa.Column("account_profile_id", UUID, nullable=True))
    op.create_foreign_key(
        op.f("fk_portfolio_snapshots_account_profile_id_brokerage_account_profiles"),
        "portfolio_snapshots", "brokerage_account_profiles",
        ["account_profile_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_portfolio_snapshots_account_profile_id_brokerage_account_profiles"),
        "portfolio_snapshots", type_="foreignkey",
    )
    op.drop_column("portfolio_snapshots", "account_profile_id")
    op.drop_constraint(
        op.f("fk_portfolio_imports_account_profile_id_brokerage_account_profiles"),
        "portfolio_imports", type_="foreignkey",
    )
    op.drop_column("portfolio_imports", "account_profile_id")
    op.drop_index(
        "ix_brokerage_account_profiles_owner_brokerage",
        table_name="brokerage_account_profiles",
    )
    op.drop_table("brokerage_account_profiles")
