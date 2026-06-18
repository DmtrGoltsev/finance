"""Dev-only seeded FastAPI surface for local PWA/Android integration."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.accounts.repository import (
    AccountRecord,
    SqlAlchemyAccountRepository,
    seed_accounts_for_tests,
)
from app.asset_categories.repository import SqlAlchemyAssetCategoryRepository
from app.auth.models import AuthMembershipRecord, AuthUserRecord
from app.auth.runtime import AuthSessionService, InMemoryCredentialStore, get_auth_session_service
from app.auth.security import HmacSha256TokenHashingBackend, Pbkdf2Sha256PasswordHashingBackend
from app.auth.session_tokens import InMemorySessionTokenStore
from app.authz import AccountOwnershipType, MembershipStatus, ResourceStatus
from app.categories.repository import CategoryRecord, SqlAlchemyCategoryRepository
from app.categories.repository import repository as category_repository
from app.categories.schemas import CategoryScope, CategoryType, RecordStatus
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.models import (
    Account,
    AssetCategory,
    Category,
    Household,
    PlanningAllocation,
    PlanningIncomeSource,
    PlanningPlan,
    User,
)
from app.db.models import Membership as DbMembership
from app.db.session import is_production_like_environment, sync_engine_for_url, sync_session_scope
from app.main import create_app
from app.planning.repository import SqlAlchemyPlanningRepository
from app.planning.router import planning_service_for_request
from app.planning.service import PlanningService
from app.transactions.repository import TransactionRecord, reset_transactions_for_tests

DEV_DEMO_EMAIL = "demo.owner@example.test"
DEV_DEMO_PASSWORD = "demo-password-only"
DEV_DEMO_USER_ID = "11111111-1111-4111-8111-111111111111"
DEV_DEMO_HOUSEHOLD_ID = "22222222-2222-4222-8222-222222222222"
DEV_DEMO_PERSONAL_ACCOUNT_ID = "33333333-3333-4333-8333-333333333333"
DEV_DEMO_SHARED_ACCOUNT_ID = "44444444-4444-4444-8444-444444444444"
DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DEV_DEMO_BROKERAGE_ACCOUNT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
DEV_DEMO_METAL_ACCOUNT_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
DEV_DEMO_PERSONAL_CATEGORY_ID = "55555555-5555-4555-8555-555555555555"
DEV_DEMO_SHARED_CATEGORY_ID = "66666666-6666-4666-8666-666666666666"
DEV_DEMO_INCOME_CATEGORY_ID = "77777777-7777-4777-8777-777777777777"
DEV_DEMO_EXPENSE_TRANSACTION_ID = "88888888-8888-4888-8888-888888888888"
DEV_DEMO_INCOME_TRANSACTION_ID = "99999999-9999-4999-8999-999999999999"
DEV_DEMO_TRANSFER_TRANSACTION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DEV_DEMO_ASSET_BUY_TRANSACTION_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
DEV_DEMO_INTEREST_TRANSACTION_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
DEV_DEMO_DIVIDEND_TRANSACTION_ID = "12121212-1212-4212-8212-121212121212"
DEV_DEMO_PLANNING_PLAN_ID = "13131313-1313-4313-8313-131313131313"
DEV_DEMO_PLANNING_INCOME_ID = "14141414-1414-4414-8414-141414141414"
DEV_DEMO_PLANNING_ALLOCATION_ID = "15151515-1515-4515-8515-151515151515"
DEV_DEMO_PLANNING_MONTH = "2026-07"

_DEV_PLANNING_TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    AssetCategory.__table__,
    Account.__table__,
    Category.__table__,
    PlanningPlan.__table__,
    PlanningIncomeSource.__table__,
    PlanningAllocation.__table__,
]


@dataclass(frozen=True, slots=True)
class DevSeedInfo:
    email: str
    password: str
    user_id: str
    household_id: str
    personal_account_id: str
    shared_account_id: str
    shared_savings_account_id: str


class DeterministicDevTokenFactory:
    def __init__(self) -> None:
        self._counter = 0

    def create_token(self) -> str:
        self._counter += 1
        return f"dev-only-token-{self._counter:04d}-not-for-production"


def create_seeded_dev_app(settings: Settings | None = None):
    app_settings = settings or get_settings()
    if is_production_like_environment(app_settings.environment):
        raise RuntimeError("Dev seed app cannot run in production-like environments.")

    application = create_app(app_settings)
    auth_service = seed_dev_surface()
    planning_database_url = seed_dev_planning_surface()
    application.dependency_overrides[get_auth_session_service] = lambda: auth_service
    application.dependency_overrides[planning_service_for_request] = (
        _seeded_dev_planning_service(planning_database_url)
    )
    application.state.dev_seed = DEV_SEED_INFO
    return application


def seed_dev_surface() -> AuthSessionService:
    """Seed process-local demo auth and finance data for local live integration only."""

    now = datetime(2026, 5, 18, 9, 0, tzinfo=UTC)
    password_hasher = Pbkdf2Sha256PasswordHashingBackend()
    auth_service = AuthSessionService(
        credentials=InMemoryCredentialStore(
            users=(
                AuthUserRecord(
                    id=DEV_DEMO_USER_ID,
                    email_normalized=DEV_DEMO_EMAIL,
                    password_hash=password_hasher.hash_password(DEV_DEMO_PASSWORD),
                    memberships=(
                        AuthMembershipRecord(
                            user_id=DEV_DEMO_USER_ID,
                            household_id=DEV_DEMO_HOUSEHOLD_ID,
                            status=MembershipStatus.ACTIVE.value,
                        ),
                    ),
                ),
            )
        ),
        sessions=InMemorySessionTokenStore(),
        password_hasher=password_hasher,
        token_hashing=HmacSha256TokenHashingBackend(
            secret=b"dev-only-token-hash-secret-32-bytes-minimum"
        ),
        token_factory=DeterministicDevTokenFactory(),
        bearer_session_ttl=timedelta(hours=12),
    )

    seed_accounts_for_tests(
        [
            AccountRecord(
                id=DEV_DEMO_PERSONAL_ACCOUNT_ID,
                name="Dev Personal Cash",
                account_type="cash",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id=DEV_DEMO_USER_ID,
                household_id=None,
                currency="USD",
                initial_balance=Decimal("1000.00"),
                current_balance=Decimal("925.50"),
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            ),
            AccountRecord(
                id=DEV_DEMO_SHARED_ACCOUNT_ID,
                name="Dev Household Card",
                account_type="card",
                ownership_type=AccountOwnershipType.SHARED,
                owner_user_id=None,
                household_id=DEV_DEMO_HOUSEHOLD_ID,
                currency="USD",
                initial_balance=Decimal("500.00"),
                current_balance=Decimal("430.25"),
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            ),
            AccountRecord(
                id=DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID,
                name="Dev Household Deposit",
                account_type="deposit",
                ownership_type=AccountOwnershipType.SHARED,
                owner_user_id=None,
                household_id=DEV_DEMO_HOUSEHOLD_ID,
                currency="USD",
                initial_balance=Decimal("100.00"),
                current_balance=Decimal("125.00"),
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            ),
            AccountRecord(
                id=DEV_DEMO_BROKERAGE_ACCOUNT_ID,
                name="Dev Brokerage",
                account_type="brokerage",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id=DEV_DEMO_USER_ID,
                household_id=None,
                currency="USD",
                initial_balance=Decimal("1000.00"),
                current_balance=Decimal("1042.00"),
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            ),
            AccountRecord(
                id=DEV_DEMO_METAL_ACCOUNT_ID,
                name="Dev Metal",
                account_type="metal",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id=DEV_DEMO_USER_ID,
                household_id=None,
                currency="USD",
                initial_balance=Decimal("500.00"),
                current_balance=Decimal("530.00"),
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                status=ResourceStatus.ACTIVE,
            ),
        ]
    )
    category_repository.reset(
        [
            CategoryRecord(
                id=DEV_DEMO_PERSONAL_CATEGORY_ID,
                name="Dev Groceries",
                type=CategoryType.EXPENSE,
                scope=CategoryScope.PERSONAL,
                owner_user_id=DEV_DEMO_USER_ID,
                household_id=None,
                icon_key="shopping-bag",
                color="#2F855A",
                status=RecordStatus.ACTIVE,
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                archived_at=None,
                deleted_at=None,
                version=1,
            ),
            CategoryRecord(
                id=DEV_DEMO_SHARED_CATEGORY_ID,
                name="Dev Home",
                type=CategoryType.EXPENSE,
                scope=CategoryScope.HOUSEHOLD,
                owner_user_id=None,
                household_id=DEV_DEMO_HOUSEHOLD_ID,
                icon_key="home",
                color="#2B6CB0",
                status=RecordStatus.ACTIVE,
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                archived_at=None,
                deleted_at=None,
                version=1,
            ),
            CategoryRecord(
                id=DEV_DEMO_INCOME_CATEGORY_ID,
                name="Dev Salary",
                type=CategoryType.INCOME,
                scope=CategoryScope.PERSONAL,
                owner_user_id=DEV_DEMO_USER_ID,
                household_id=None,
                icon_key="wallet",
                color="#805AD5",
                status=RecordStatus.ACTIVE,
                created_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                archived_at=None,
                deleted_at=None,
                version=1,
            ),
        ]
    )
    reset_transactions_for_tests(
        [
            TransactionRecord(
                id=DEV_DEMO_EXPENSE_TRANSACTION_ID,
                transaction_type="expense",
                account_id=DEV_DEMO_SHARED_ACCOUNT_ID,
                counterparty_account_id=None,
                category_id=DEV_DEMO_SHARED_CATEGORY_ID,
                amount=Decimal("69.75"),
                currency="USD",
                occurred_at=datetime(2026, 5, 17, 12, 30, tzinfo=UTC),
                description="Dev household supplies",
                source_type="manual",
                transfer_scope=None,
                transfer_status=None,
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
            TransactionRecord(
                id=DEV_DEMO_INCOME_TRANSACTION_ID,
                transaction_type="income",
                account_id=DEV_DEMO_PERSONAL_ACCOUNT_ID,
                counterparty_account_id=None,
                category_id=DEV_DEMO_INCOME_CATEGORY_ID,
                amount=Decimal("250.00"),
                currency="USD",
                occurred_at=datetime(2026, 5, 18, 8, 0, tzinfo=UTC),
                description="Dev sample income",
                source_type="manual",
                transfer_scope=None,
                transfer_status=None,
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
            TransactionRecord(
                id=DEV_DEMO_TRANSFER_TRANSACTION_ID,
                transaction_type="transfer",
                account_id=DEV_DEMO_SHARED_ACCOUNT_ID,
                counterparty_account_id=DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID,
                category_id=None,
                amount=Decimal("25.00"),
                currency="USD",
                occurred_at=datetime(2026, 5, 18, 8, 30, tzinfo=UTC),
                description="Dev same-household transfer",
                source_type="manual",
                transfer_scope="household_same_household",
                transfer_status="posted",
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
            TransactionRecord(
                id=DEV_DEMO_ASSET_BUY_TRANSACTION_ID,
                transaction_type="asset_buy",
                account_id=DEV_DEMO_BROKERAGE_ACCOUNT_ID,
                counterparty_account_id=None,
                category_id=None,
                amount=Decimal("300.00"),
                currency="USD",
                occurred_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC),
                description="Dev brokerage asset buy",
                source_type="manual",
                transfer_scope=None,
                transfer_status=None,
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
            TransactionRecord(
                id=DEV_DEMO_INTEREST_TRANSACTION_ID,
                transaction_type="interest",
                account_id=DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID,
                counterparty_account_id=None,
                category_id=None,
                amount=Decimal("5.00"),
                currency="USD",
                occurred_at=datetime(2026, 5, 18, 9, 30, tzinfo=UTC),
                description="Dev deposit interest",
                source_type="manual",
                transfer_scope=None,
                transfer_status=None,
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
            TransactionRecord(
                id=DEV_DEMO_DIVIDEND_TRANSACTION_ID,
                transaction_type="dividend",
                account_id=DEV_DEMO_BROKERAGE_ACCOUNT_ID,
                counterparty_account_id=None,
                category_id=None,
                amount=Decimal("7.50"),
                currency="USD",
                occurred_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
                description="Dev brokerage dividend",
                source_type="manual",
                transfer_scope=None,
                transfer_status=None,
                record_status="active",
                created_by_user_id=DEV_DEMO_USER_ID,
                last_edited_by_user_id=DEV_DEMO_USER_ID,
                created_at=now,
                updated_at=now,
                deleted_at=None,
                version=1,
            ),
        ]
    )
    return auth_service


def seed_dev_planning_surface() -> str:
    """Seed a dev-only SQLite planning runtime independent from external PostgreSQL."""

    database_url = (
        f"sqlite+pysqlite:///file:finance_dev_seed_planning_{uuid4().hex}"
        "?mode=memory&cache=shared&uri=true"
    )
    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=_DEV_PLANNING_TABLES)

    now = datetime(2026, 5, 18, 9, 0, tzinfo=UTC)
    user_id = UUID(DEV_DEMO_USER_ID)
    household_id = UUID(DEV_DEMO_HOUSEHOLD_ID)
    personal_account_id = UUID(DEV_DEMO_PERSONAL_ACCOUNT_ID)
    shared_account_id = UUID(DEV_DEMO_SHARED_ACCOUNT_ID)
    shared_savings_account_id = UUID(DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID)
    brokerage_account_id = UUID(DEV_DEMO_BROKERAGE_ACCOUNT_ID)
    metal_account_id = UUID(DEV_DEMO_METAL_ACCOUNT_ID)
    personal_category_id = UUID(DEV_DEMO_PERSONAL_CATEGORY_ID)
    shared_category_id = UUID(DEV_DEMO_SHARED_CATEGORY_ID)
    income_category_id = UUID(DEV_DEMO_INCOME_CATEGORY_ID)
    plan_id = UUID(DEV_DEMO_PLANNING_PLAN_ID)

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add(
            User(
                id=user_id,
                email_normalized=DEV_DEMO_EMAIL,
                password_hash="dev-seed-auth-is-process-local",
                display_name="Demo Owner",
                auth_status="active",
                record_status="active",
                session_version=1,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.add(
            Household(
                id=household_id,
                name="Dev Household",
                created_by_user_id=user_id,
                status="active",
                record_status="active",
                membership_version=1,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.add(
            DbMembership(
                id=uuid4(),
                household_id=household_id,
                user_id=user_id,
                membership_status="active",
                joined_at=now,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.add_all(
            [
                _db_account(
                    id=personal_account_id,
                    name="Dev Personal Cash",
                    account_type="cash",
                    ownership_type="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    current_balance=Decimal("925.50"),
                    created_at=now,
                ),
                _db_account(
                    id=shared_account_id,
                    name="Dev Household Card",
                    account_type="card",
                    ownership_type="shared",
                    owner_user_id=None,
                    household_id=household_id,
                    current_balance=Decimal("430.25"),
                    created_at=now,
                ),
                _db_account(
                    id=shared_savings_account_id,
                    name="Dev Household Deposit",
                    account_type="deposit",
                    ownership_type="shared",
                    owner_user_id=None,
                    household_id=household_id,
                    current_balance=Decimal("125.00"),
                    created_at=now,
                ),
                _db_account(
                    id=brokerage_account_id,
                    name="Dev Brokerage",
                    account_type="brokerage",
                    ownership_type="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    current_balance=Decimal("1042.00"),
                    created_at=now,
                ),
                _db_account(
                    id=metal_account_id,
                    name="Dev Metal",
                    account_type="metal",
                    ownership_type="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    current_balance=Decimal("530.00"),
                    created_at=now,
                ),
            ]
        )
        session.add_all(
            [
                _db_category(
                    id=personal_category_id,
                    name="Dev Groceries",
                    category_type="expense",
                    category_scope="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    icon_key="shopping-bag",
                    color="#2F855A",
                    created_at=now,
                ),
                _db_category(
                    id=shared_category_id,
                    name="Dev Home",
                    category_type="expense",
                    category_scope="household",
                    owner_user_id=None,
                    household_id=household_id,
                    icon_key="home",
                    color="#2B6CB0",
                    created_at=now,
                ),
                _db_category(
                    id=income_category_id,
                    name="Dev Salary",
                    category_type="income",
                    category_scope="personal",
                    owner_user_id=user_id,
                    household_id=None,
                    icon_key="wallet",
                    color="#805AD5",
                    created_at=now,
                ),
            ]
        )
        session.add(
            PlanningPlan(
                id=plan_id,
                scope_type="personal",
                owner_user_id=user_id,
                household_id=None,
                plan_month=date(2026, 7, 1),
                currency="USD",
                created_by_user_id=user_id,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.add(
            PlanningIncomeSource(
                id=UUID(DEV_DEMO_PLANNING_INCOME_ID),
                plan_id=plan_id,
                amount=Decimal("3000.0000"),
                source="Dev salary plan",
                description="Seeded planning income",
                day_of_month=5,
                confirmation_state="planned",
                created_by_user_id=user_id,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.add(
            PlanningAllocation(
                id=UUID(DEV_DEMO_PLANNING_ALLOCATION_ID),
                plan_id=plan_id,
                target_type="expense_category",
                target_id=personal_category_id,
                target_snapshot={
                    "targetType": "expense_category",
                    "id": DEV_DEMO_PERSONAL_CATEGORY_ID,
                    "name": "Dev Groceries",
                    "categoryType": "expense",
                    "scope": "personal",
                    "ownerUserId": DEV_DEMO_USER_ID,
                    "householdId": None,
                },
                requires_attention=False,
                allocation_mode="amount",
                allocation_value=Decimal("450.0000"),
                created_by_user_id=user_id,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )
        session.flush()

    return database_url


def _seeded_dev_planning_service(database_url: str):
    def override() -> Iterator[PlanningService]:
        settings = get_settings().model_copy(update={"database_url": database_url})
        with sync_session_scope(settings) as session:
            yield PlanningService(
                SqlAlchemyPlanningRepository(session),
                SqlAlchemyAccountRepository(session),
                SqlAlchemyCategoryRepository(session),
                SqlAlchemyAssetCategoryRepository(session),
            )

    return override


def _db_account(
    *,
    id: UUID,
    name: str,
    account_type: str,
    ownership_type: str,
    owner_user_id: UUID | None,
    household_id: UUID | None,
    current_balance: Decimal,
    created_at: datetime,
) -> Account:
    return Account(
        id=id,
        name=name,
        account_type=account_type,
        ownership_type=ownership_type,
        owner_user_id=owner_user_id,
        household_id=household_id,
        currency="USD",
        initial_balance_amount=current_balance,
        current_balance_amount=current_balance,
        record_status="active",
        created_by_user_id=UUID(DEV_DEMO_USER_ID),
        created_at=created_at,
        updated_at=created_at,
        version=1,
    )


def _db_category(
    *,
    id: UUID,
    name: str,
    category_type: str,
    category_scope: str,
    owner_user_id: UUID | None,
    household_id: UUID | None,
    icon_key: str,
    color: str,
    created_at: datetime,
) -> Category:
    return Category(
        id=id,
        name=name,
        category_type=category_type,
        category_scope=category_scope,
        owner_user_id=owner_user_id,
        household_id=household_id,
        icon_key=icon_key,
        color=color,
        record_status="active",
        created_by_user_id=UUID(DEV_DEMO_USER_ID),
        created_at=created_at,
        updated_at=created_at,
        version=1,
    )


DEV_SEED_INFO = DevSeedInfo(
    email=DEV_DEMO_EMAIL,
    password=DEV_DEMO_PASSWORD,
    user_id=DEV_DEMO_USER_ID,
    household_id=DEV_DEMO_HOUSEHOLD_ID,
    personal_account_id=DEV_DEMO_PERSONAL_ACCOUNT_ID,
    shared_account_id=DEV_DEMO_SHARED_ACCOUNT_ID,
    shared_savings_account_id=DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID,
)


app = create_seeded_dev_app()
