"""Dev-only seeded FastAPI surface for local PWA/Android integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.accounts.repository import AccountRecord, seed_accounts_for_tests
from app.auth.models import AuthMembershipRecord, AuthUserRecord
from app.auth.runtime import AuthSessionService, InMemoryCredentialStore, get_auth_session_service
from app.auth.security import HmacSha256TokenHashingBackend, Pbkdf2Sha256PasswordHashingBackend
from app.auth.session_tokens import InMemorySessionTokenStore
from app.authz import AccountOwnershipType, MembershipStatus, ResourceStatus
from app.categories.repository import CategoryRecord
from app.categories.repository import repository as category_repository
from app.categories.schemas import CategoryScope, CategoryType, RecordStatus
from app.config import Settings, get_settings
from app.db.session import is_production_like_environment
from app.main import create_app
from app.transactions.repository import TransactionRecord, reset_transactions_for_tests

DEV_DEMO_EMAIL = "demo.owner@example.test"
DEV_DEMO_PASSWORD = "demo-password-only"
DEV_DEMO_USER_ID = "11111111-1111-4111-8111-111111111111"
DEV_DEMO_HOUSEHOLD_ID = "22222222-2222-4222-8222-222222222222"
DEV_DEMO_PERSONAL_ACCOUNT_ID = "33333333-3333-4333-8333-333333333333"
DEV_DEMO_SHARED_ACCOUNT_ID = "44444444-4444-4444-8444-444444444444"
DEV_DEMO_SHARED_SAVINGS_ACCOUNT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DEV_DEMO_PERSONAL_CATEGORY_ID = "55555555-5555-4555-8555-555555555555"
DEV_DEMO_SHARED_CATEGORY_ID = "66666666-6666-4666-8666-666666666666"
DEV_DEMO_INCOME_CATEGORY_ID = "77777777-7777-4777-8777-777777777777"
DEV_DEMO_EXPENSE_TRANSACTION_ID = "88888888-8888-4888-8888-888888888888"
DEV_DEMO_INCOME_TRANSACTION_ID = "99999999-9999-4999-8999-999999999999"
DEV_DEMO_TRANSFER_TRANSACTION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


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
    application.dependency_overrides[get_auth_session_service] = lambda: auth_service
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
                account_type="bank",
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
                name="Dev Household Savings",
                account_type="bank",
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
        ]
    )
    return auth_service


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
