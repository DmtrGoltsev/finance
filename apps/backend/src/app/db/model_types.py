"""Reusable SQLAlchemy column helpers for the model skeleton."""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, text
from sqlalchemy.orm import MappedColumn, mapped_column
from sqlalchemy.types import Uuid


MONEY_NUMERIC = Numeric(20, 4)


def uuid_pk() -> MappedColumn[Any]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def uuid_fk(target: str, *, nullable: bool = False) -> MappedColumn[Any]:
    return mapped_column(Uuid(as_uuid=True), ForeignKey(target), nullable=nullable)


def created_timestamp() -> MappedColumn[Any]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


def updated_timestamp() -> MappedColumn[Any]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
