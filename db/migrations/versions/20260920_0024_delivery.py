"""Durable outbox leases and session-bound push registrations."""

import sqlalchemy as sa
from alembic import op

revision = "20260920_0024"
down_revision = "20260920_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("outbox_events", sa.Column("lease_token", sa.Uuid()))
    op.add_column("outbox_events", sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.add_column(
        "outbox_events",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("token", sa.Text(), unique=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("outbox_events.id"), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("push_devices.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.UniqueConstraint("event_id", "device_id"),
    )


def downgrade():
    # Stop workers before rollback. Preserve identity while discarding the lease mechanism.
    op.execute(
        sa.text(
            "UPDATE outbox_events SET status='pending', available_at=CURRENT_TIMESTAMP "
            "WHERE status='processing'"
        )
    )
    op.drop_table("push_deliveries")
    op.drop_table("push_devices")
    for name in ("delivery_attempts", "lease_until", "lease_token"):
        op.drop_column("outbox_events", name)
