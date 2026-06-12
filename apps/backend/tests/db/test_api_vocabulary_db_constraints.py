from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Account, Category, Household, Transaction, User
from app.db.models import Membership as DbMembership

BASE_TIME = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    Account.__table__,
    Category.__table__,
    Transaction.__table__,
]


def test_account_api_vocabulary_persists_through_sqlalchemy_constraints() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    user_id = uuid4()

    with Session(engine, future=True) as session:
        _seed_user(session, user_id)
        for account_type in ("cash", "bank", "deposit", "brokerage", "card", "metal", "other"):
            session.add(
                Account(
                    id=uuid4(),
                    name=f"{account_type} account",
                    account_type=account_type,
                    ownership_type="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    currency="RUB",
                    initial_balance_amount=Decimal("1.0000"),
                    current_balance_amount=Decimal("1.0000"),
                    record_status="active",
                    created_by_user_id=user_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )

        session.flush()


def test_transaction_api_vocabulary_persists_through_sqlalchemy_constraints() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    user_id = uuid4()
    account_id = uuid4()
    counterparty_account_id = uuid4()
    category_id = uuid4()

    with Session(engine, future=True) as session:
        _seed_user(session, user_id)
        _seed_account(session, account_id, user_id)
        _seed_account(session, counterparty_account_id, user_id)
        session.add(
            Category(
                id=category_id,
                name="Income or expense category",
                category_type="expense",
                category_scope="personal",
                owner_user_id=user_id,
                household_id=None,
                icon_key="tag",
                color="#336699",
                record_status="active",
                created_by_user_id=user_id,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            )
        )

        for offset, transaction_type in enumerate(
            (
                "income",
                "expense",
                "transfer",
                "brokerage",
                "asset_buy",
                "asset_sell",
                "interest",
                "dividend",
                "adjustment",
            ),
            start=1,
        ):
            is_transfer = transaction_type == "transfer"
            session.add(
                Transaction(
                    id=uuid4(),
                    transaction_type=transaction_type,
                    account_id=account_id,
                    counterparty_account_id=counterparty_account_id if is_transfer else None,
                    category_id=category_id if transaction_type in {"income", "expense"} else None,
                    amount=Decimal("1.0000"),
                    currency="RUB",
                    occurred_at=BASE_TIME + timedelta(minutes=offset),
                    transaction_date=(BASE_TIME + timedelta(minutes=offset)).date(),
                    description=f"{transaction_type} vocabulary proof",
                    source_type="manual",
                    transfer_scope="personal_same_owner" if is_transfer else None,
                    transfer_status="posted" if is_transfer else None,
                    record_status="active",
                    created_by_user_id=user_id,
                    last_edited_by_user_id=user_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )

        session.flush()


def _seed_user(session: Session, user_id) -> None:  # type: ignore[no-untyped-def]
    session.add(
        User(
            id=user_id,
            email_normalized="owner@example.test",
            password_hash="hash-placeholder",
            display_name="Owner",
            auth_status="active",
            record_status="active",
            session_version=1,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            version=1,
        )
    )


def _seed_account(session: Session, account_id, user_id) -> None:  # type: ignore[no-untyped-def]
    session.add(
        Account(
            id=account_id,
            name=f"Account {account_id}",
            account_type="cash",
            ownership_type="personal",
            owner_user_id=user_id,
            household_id=None,
            currency="RUB",
            initial_balance_amount=Decimal("10.0000"),
            current_balance_amount=Decimal("10.0000"),
            record_status="active",
            created_by_user_id=user_id,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            version=1,
        )
    )
