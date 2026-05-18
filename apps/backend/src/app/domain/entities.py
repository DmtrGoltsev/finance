"""Minimal domain records for authorization-oriented tests.

These dataclasses are deliberately persistence-agnostic. They model the fields
authz predicates need to inspect without duplicating predicate logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import (
    AccountType,
    CategoryScope,
    CategoryType,
    MembershipStatus,
    OwnershipType,
    RecordStatus,
    SourceType,
    TransactionType,
    TransferScope,
)
from .money import Money


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    name: str
    account_type: AccountType
    ownership_type: OwnershipType
    currency: str
    owner_user_id: str | None = None
    household_id: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class Category:
    id: str
    name: str
    scope: CategoryScope
    category_type: CategoryType
    owner_user_id: str | None = None
    household_id: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    transaction_type: TransactionType
    account_id: str
    money: Money
    occurred_at: datetime
    source_type: SourceType = SourceType.MANUAL
    category_id: str | None = None
    counterparty_account_id: str | None = None
    transfer_scope: TransferScope | None = None
    created_by_user_id: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class Membership:
    id: str
    user_id: str
    household_id: str
    status: MembershipStatus
