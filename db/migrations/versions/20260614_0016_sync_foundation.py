"""Add sync foundation tables.

Revision ID: 20260614_0016
Revises: 20260612_0015
Create Date: 2026-06-14

Rollback notes:
- Downgrade drops only the additive sync state/change-log tables.
- No business CRUD tables or financial rows are modified.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260614_0016"
down_revision: str | None = "20260612_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
SYNC_SEQ = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "sync_clients",
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("client_schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "server_cursor",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "length(device_id) > 0",
            name=op.f("ck_sync_clients_device_id_not_empty"),
        ),
        sa.CheckConstraint(
            "client_schema_version > 0",
            name=op.f("ck_sync_clients_positive_client_schema_version"),
        ),
        sa.CheckConstraint(
            "server_cursor >= 0",
            name=op.f("ck_sync_clients_non_negative_server_cursor"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_sync_clients_actor_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("actor_user_id", "device_id", name=op.f("pk_sync_clients")),
    )
    op.create_index(
        "ix_sync_clients_actor_last_seen",
        "sync_clients",
        ["actor_user_id", sa.text("last_seen_at DESC")],
    )

    op.create_table(
        "sync_changes",
        sa.Column("seq", SYNC_SEQ, autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("household_id", UUID, nullable=True),
        sa.Column("entity_version", sa.BigInteger(), nullable=True),
        sa.Column("entity_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by_user_id", UUID, nullable=True),
        sa.Column("client_mutation_id", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("tombstone_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("seq > 0", name=op.f("ck_sync_changes_positive_seq")),
        sa.CheckConstraint(
            "length(entity_type) > 0",
            name=op.f("ck_sync_changes_entity_type_not_empty"),
        ),
        sa.CheckConstraint(
            "length(change_type) > 0",
            name=op.f("ck_sync_changes_change_type_not_empty"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('personal', 'household', 'system')",
            name=op.f("ck_sync_changes_scope_type_valid"),
        ),
        sa.CheckConstraint(
            "(scope_type = 'personal' AND owner_user_id IS NOT NULL AND household_id IS NULL) "
            "OR (scope_type = 'household' AND household_id IS NOT NULL AND owner_user_id IS NULL) "
            "OR (scope_type = 'system' AND owner_user_id IS NULL AND household_id IS NULL)",
            name=op.f("ck_sync_changes_sync_scope_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_sync_changes_owner_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_sync_changes_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_sync_changes_changed_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_sync_changes")),
    )
    op.create_index("ix_sync_changes_seq", "sync_changes", ["seq"])
    op.create_index("ix_sync_changes_entity", "sync_changes", ["entity_type", "entity_id", "seq"])
    op.create_index(
        "ix_sync_changes_owner_visibility",
        "sync_changes",
        ["owner_user_id", "scope_type", "seq"],
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
        sqlite_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_sync_changes_household_visibility",
        "sync_changes",
        ["household_id", "scope_type", "seq"],
        postgresql_where=sa.text("household_id IS NOT NULL"),
        sqlite_where=sa.text("household_id IS NOT NULL"),
    )

    op.create_table(
        "sync_client_mutations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("client_mutation_id", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID, nullable=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("change_seq", sa.BigInteger(), nullable=True),
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
        sa.CheckConstraint(
            "length(device_id) > 0",
            name=op.f("ck_sync_client_mutations_device_id_not_empty"),
        ),
        sa.CheckConstraint(
            "length(client_mutation_id) > 0",
            name=op.f("ck_sync_client_mutations_client_mutation_id_not_empty"),
        ),
        sa.CheckConstraint(
            "length(request_hash) > 0",
            name=op.f("ck_sync_client_mutations_request_hash_not_empty"),
        ),
        sa.CheckConstraint(
            "length(entity_type) > 0",
            name=op.f("ck_sync_client_mutations_entity_type_not_empty"),
        ),
        sa.CheckConstraint(
            "length(operation) > 0",
            name=op.f("ck_sync_client_mutations_operation_not_empty"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'failed')",
            name=op.f("ck_sync_client_mutations_status_valid"),
        ),
        sa.CheckConstraint(
            "change_seq IS NULL OR change_seq > 0",
            name=op.f("ck_sync_client_mutations_positive_change_seq"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_sync_client_mutations_actor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id", "device_id"],
            ["sync_clients.actor_user_id", "sync_clients.device_id"],
            name=op.f("fk_sync_client_mutations_actor_device_sync_clients"),
        ),
        sa.UniqueConstraint(
            "actor_user_id",
            "device_id",
            "client_mutation_id",
            name=op.f("uq_sync_client_mutations_actor_device_client_mutation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_client_mutations")),
    )
    op.create_index(
        "ix_sync_client_mutations_actor_status_created",
        "sync_client_mutations",
        ["actor_user_id", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_sync_client_mutations_entity",
        "sync_client_mutations",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_sync_client_mutations_change_seq",
        "sync_client_mutations",
        ["change_seq"],
        postgresql_where=sa.text("change_seq IS NOT NULL"),
        sqlite_where=sa.text("change_seq IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_sync_client_mutations_change_seq", table_name="sync_client_mutations")
    op.drop_index("ix_sync_client_mutations_entity", table_name="sync_client_mutations")
    op.drop_index(
        "ix_sync_client_mutations_actor_status_created",
        table_name="sync_client_mutations",
    )
    op.drop_table("sync_client_mutations")

    op.drop_index("ix_sync_changes_household_visibility", table_name="sync_changes")
    op.drop_index("ix_sync_changes_owner_visibility", table_name="sync_changes")
    op.drop_index("ix_sync_changes_entity", table_name="sync_changes")
    op.drop_index("ix_sync_changes_seq", table_name="sync_changes")
    op.drop_table("sync_changes")

    op.drop_index("ix_sync_clients_actor_last_seen", table_name="sync_clients")
    op.drop_table("sync_clients")
