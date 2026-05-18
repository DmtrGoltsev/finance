from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.accounts.repository import SqlAlchemyAccountRepository
from app.accounts.service import AccountNotFoundOrInaccessible, AccountService
from app.authz import (
    AccountOwnershipType,
    Actor,
    Membership,
    MembershipStatus,
    ResourceStatus,
)
from app.categories.repository import SqlAlchemyCategoryRepository
from app.categories.schemas import CategoryScope, CategoryType
from app.categories.schemas import RecordStatus as CategoryRecordStatus
from app.categories.service import CategoryService
from app.db.base import Base
from app.db.models import Account, Category, Household, User
from app.db.models import Membership as DbMembership

BASE_TIME = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
SLICE_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    Account.__table__,
    Category.__table__,
]


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=SLICE_TABLES)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        yield session


def _user(user_id: UUID, label: str) -> User:
    return User(
        id=user_id,
        email_normalized=f"{label}@example.test",
        password_hash="hash-placeholder",
        display_name=label,
        auth_status="active",
        record_status="active",
        session_version=1,
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
        version=1,
    )


def _seed_principals(
    session: Session,
    *,
    owner_id: UUID,
    member_id: UUID,
    invited_id: UUID,
    household_id: UUID,
) -> None:
    session.add_all(
        [
            _user(owner_id, "owner"),
            _user(member_id, "member"),
            _user(invited_id, "invited"),
            Household(
                id=household_id,
                name="Family",
                created_by_user_id=owner_id,
                status="active",
                record_status="active",
                membership_version=1,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            ),
            DbMembership(
                id=uuid4(),
                household_id=household_id,
                user_id=owner_id,
                membership_status="active",
                joined_at=BASE_TIME,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            ),
            DbMembership(
                id=uuid4(),
                household_id=household_id,
                user_id=member_id,
                membership_status="active",
                joined_at=BASE_TIME,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            ),
            DbMembership(
                id=uuid4(),
                household_id=household_id,
                user_id=invited_id,
                membership_status="invited",
                invited_at=BASE_TIME,
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            ),
        ]
    )


def _actor(user_id: UUID, household_id: UUID, status: MembershipStatus) -> Actor:
    user_id_text = str(user_id)
    return Actor(
        user_id=user_id_text,
        request_id=f"req-{user_id_text}",
        memberships=(Membership(user_id_text, str(household_id), status),),
    )


def test_sqlalchemy_repositories_persist_accounts_categories_and_color() -> None:
    factory = _session_factory()
    owner_id = uuid4()
    household_id = uuid4()
    invited_id = uuid4()

    for session in _session_scope(factory):
        _seed_principals(
            session,
            owner_id=owner_id,
            member_id=uuid4(),
            invited_id=invited_id,
            household_id=household_id,
        )
        session.commit()

    for session in _session_scope(factory):
        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)

        account = accounts.create(
            name="DB Wallet",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("123.4500"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        category = categories.create(
            name="Groceries",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.HOUSEHOLD,
            owner_user_id=None,
            household_id=str(household_id),
            icon_key="cart",
            color="#336699",
            created_by_user_id=str(owner_id),
        )
        session.commit()
        account_id = account.id
        category_id = category.id

    archived_at = datetime(2026, 5, 17, 13, 0, tzinfo=UTC)
    for session in _session_scope(factory):
        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)

        fetched_account = accounts.get(account_id)
        assert fetched_account is not None
        assert fetched_account.owner_user_id == str(owner_id)
        assert fetched_account.current_balance == Decimal("123.4500")

        archived_account = accounts.save(
            replace(
                fetched_account,
                name="Archived DB Wallet",
                status=ResourceStatus.ARCHIVED,
                archived_at=archived_at,
            )
        )
        assert archived_account.version == 2

        fetched_category = categories.get(category_id)
        assert fetched_category is not None
        assert fetched_category.household_id == str(household_id)
        assert fetched_category.color == "#336699"

        archived_category = categories.save(
            replace(
                fetched_category,
                color="#112233",
                status=CategoryRecordStatus.ARCHIVED,
                archived_at=archived_at,
            )
        )
        assert archived_category.version == 2
        session.commit()

    for session in _session_scope(factory):
        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)

        assert accounts.get(account_id).name == "Archived DB Wallet"  # type: ignore[union-attr]
        persisted_category = categories.get(category_id)
        assert persisted_category is not None
        assert persisted_category.color == "#112233"
        assert persisted_category.status == CategoryRecordStatus.ARCHIVED
        assert accounts.get("acct-not-a-uuid") is None
        assert categories.get("cat-not-a-uuid") is None


def test_db_backed_service_wiring_preserves_accounts_categories_privacy() -> None:
    factory = _session_factory()
    owner_id = uuid4()
    member_id = uuid4()
    invited_id = uuid4()
    household_id = uuid4()

    for session in _session_scope(factory):
        _seed_principals(
            session,
            owner_id=owner_id,
            member_id=member_id,
            invited_id=invited_id,
            household_id=household_id,
        )
        accounts = SqlAlchemyAccountRepository(session)
        categories = SqlAlchemyCategoryRepository(session)
        accounts.create(
            name="Owner Personal",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("10.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        member_account = accounts.create(
            name="Member Personal",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("20.0000"),
            created_by_user_id=str(member_id),
            owner_user_id=str(member_id),
            household_id=None,
        )
        shared_account = accounts.create(
            name="Shared",
            account_type="cash",
            ownership_type=AccountOwnershipType.SHARED,
            currency="RUB",
            initial_balance=Decimal("30.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=None,
            household_id=str(household_id),
        )
        categories.create(
            name="Owner Food",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            icon_key=None,
            color=None,
            created_by_user_id=str(owner_id),
        )
        categories.create(
            name="Shared Food",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.HOUSEHOLD,
            owner_user_id=None,
            household_id=str(household_id),
            icon_key=None,
            color="#445566",
            created_by_user_id=str(owner_id),
        )
        session.commit()

    for session in _session_scope(factory):
        account_service = AccountService(SqlAlchemyAccountRepository(session))
        category_service = CategoryService(SqlAlchemyCategoryRepository(session))
        owner_actor = _actor(owner_id, household_id, MembershipStatus.ACTIVE)
        member_actor = _actor(member_id, household_id, MembershipStatus.ACTIVE)
        invited_actor = _actor(invited_id, household_id, MembershipStatus.INVITED)

        owner_accounts, _, _ = account_service.list_accounts(actor=owner_actor, limit=50)
        assert {record.name for record in owner_accounts} == {"Owner Personal", "Shared"}

        member_accounts, _, _ = account_service.list_accounts(actor=member_actor, limit=50)
        assert {record.name for record in member_accounts} == {"Member Personal", "Shared"}

        invited_accounts, _, _ = account_service.list_accounts(actor=invited_actor, limit=50)
        assert invited_accounts == []

        with_missing_shape = account_service.get_account
        try:
            with_missing_shape(actor=owner_actor, account_id=member_account.id)
        except AccountNotFoundOrInaccessible:
            pass
        else:  # pragma: no cover - explicit privacy assertion
            raise AssertionError("foreign personal account was visible through DB-backed service")

        try:
            with_missing_shape(actor=invited_actor, account_id=shared_account.id)
        except AccountNotFoundOrInaccessible:
            pass
        else:  # pragma: no cover - explicit privacy assertion
            raise AssertionError(
                "invited member could read shared account through DB-backed service"
            )

        owner_categories, owner_page = category_service.list(
            actor=owner_actor,
            limit=50,
            cursor=None,
            scope=None,
            type=None,
            household_id=None,
            status_filter=None,
            q=None,
            sort=None,
        )
        assert owner_page.has_more is False
        assert {item.name for item in owner_categories} == {"Owner Food", "Shared Food"}

        invited_categories, _ = category_service.list(
            actor=invited_actor,
            limit=50,
            cursor=None,
            scope=None,
            type=None,
            household_id=None,
            status_filter=None,
            q=None,
            sort=None,
        )
        assert invited_categories == []
