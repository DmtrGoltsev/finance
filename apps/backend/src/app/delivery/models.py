from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_types import uuid_fk, uuid_pk


class PushDevice(Base):
    __tablename__ = "push_devices"
    id: Mapped[UUID] = uuid_pk()
    owner_user_id: Mapped[UUID] = uuid_fk("users.id")
    session_id: Mapped[UUID] = uuid_fk("sessions.id")
    token: Mapped[str | None] = mapped_column(Text, unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (UniqueConstraint("event_id", "device_id"),)
    id: Mapped[UUID] = uuid_pk()
    event_id: Mapped[UUID] = uuid_fk("outbox_events.id")
    device_id: Mapped[UUID] = uuid_fk("push_devices.id")
    session_id: Mapped[UUID] = uuid_fk("sessions.id")
    status: Mapped[str] = mapped_column(Text)
