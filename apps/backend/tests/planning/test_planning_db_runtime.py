from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.accounts.repository import SqlAlchemyAccountRepository
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.asset_categories.repository import SqlAlchemyAssetCategoryRepository
from app.asset_categories.schemas import AssetCategoryScope, AssetCategoryType
from app.authz import AccountOwnershipType, Actor, Membership, MembershipStatus
from app.categories.repository import SqlAlchemyCategoryRepository
from app.categories.schemas import CategoryScope, CategoryType
from app.config import get_settings
from app.db.base import Base
from app.db.models import (
    Account,
    AccountBalanceSnapshot,
    AssetCategory,
    Category,
    Household,
    PlanningAllocation,
    PlanningIncomeSource,
    PlanningPlan,
    SyncChange,
    Transaction,
    User,
)
from app.db.models import Membership as DbMembership
from app.db.session import sync_engine_for_url
from app.main import create_app

BASE_TIME = datetime(2026, 6, 6, 12, 0, tzinfo=UTC)
TABLES = [
    User.__table__,
    Household.__table__,
    DbMembership.__table__,
    AssetCategory.__table__,
    Account.__table__,
    AccountBalanceSnapshot.__table__,
    Category.__table__,
    Transaction.__table__,
    PlanningPlan.__table__,
    PlanningIncomeSource.__table__,
    PlanningAllocation.__table__,
    SyncChange.__table__,
]


def _app_for_actor(actor: Actor) -> FastAPI:
    app = create_app()
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    return app


@contextmanager
def _client_for_actor(actor: Actor) -> Iterator[TestClient]:
    with TestClient(_app_for_actor(actor)) as client:
        yield client


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


def _actor(
    user_id: UUID,
    memberships: tuple[tuple[UUID, MembershipStatus], ...] = (),
) -> Actor:
    user_id_text = str(user_id)
    return Actor(
        user_id=user_id_text,
        request_id=f"req-{user_id_text}",
        memberships=tuple(
            Membership(
                user_id=user_id_text,
                household_id=str(household_id),
                status=status,
            )
            for household_id, status in memberships
        ),
    )


@pytest.fixture
def planning_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, Any]]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'planning.sqlite').as_posix()}"
    monkeypatch.setenv("FINANCE_BACKEND_DATABASE_URL", database_url)
    monkeypatch.setenv("FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE", "db")
    get_settings.cache_clear()

    engine = sync_engine_for_url(database_url)
    Base.metadata.create_all(engine, tables=TABLES)

    owner_id = uuid4()
    member_id = uuid4()
    other_id = uuid4()
    invited_id = uuid4()
    former_id = uuid4()
    household_id = uuid4()
    other_household_id = uuid4()

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add_all(
            [
                _user(owner_id, "owner"),
                _user(member_id, "member"),
                _user(other_id, "other"),
                _user(invited_id, "invited"),
                _user(former_id, "former"),
                Household(
                    id=household_id,
                    name="Owner Household",
                    created_by_user_id=owner_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                Household(
                    id=other_household_id,
                    name="Other Household",
                    created_by_user_id=other_id,
                    status="active",
                    record_status="active",
                    membership_version=1,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
            ]
        )
        for user_id, household, status in (
            (owner_id, household_id, "active"),
            (member_id, household_id, "active"),
            (invited_id, household_id, "invited"),
            (former_id, household_id, "left"),
            (other_id, other_household_id, "active"),
        ):
            session.add(
                DbMembership(
                    id=uuid4(),
                    household_id=household,
                    user_id=user_id,
                    membership_status=status,
                    invited_at=BASE_TIME if status == "invited" else None,
                    joined_at=BASE_TIME if status == "active" else None,
                    ended_at=BASE_TIME if status == "left" else None,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                )
            )

        accounts = SqlAlchemyAccountRepository(session)
        asset_categories = SqlAlchemyAssetCategoryRepository(session)
        categories = SqlAlchemyCategoryRepository(session)
        owner_account = accounts.create(
            name="Owner Cash",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("100.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        owner_asset_account = accounts.create(
            name="Owner Brokerage",
            account_type="brokerage",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("1000.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        member_account = accounts.create(
            name="Member Cash",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="RUB",
            initial_balance=Decimal("200.0000"),
            created_by_user_id=str(member_id),
            owner_user_id=str(member_id),
            household_id=None,
        )
        shared_account = accounts.create(
            name="Shared Cash",
            account_type="cash",
            ownership_type=AccountOwnershipType.SHARED,
            currency="RUB",
            initial_balance=Decimal("300.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=None,
            household_id=str(household_id),
        )
        usd_account = accounts.create(
            name="Owner USD",
            account_type="cash",
            ownership_type=AccountOwnershipType.PERSONAL,
            currency="USD",
            initial_balance=Decimal("10.0000"),
            created_by_user_id=str(owner_id),
            owner_user_id=str(owner_id),
            household_id=None,
        )
        owner_investment_category = asset_categories.create(
            name="Owner Investments",
            scope_type=AssetCategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            currency="RUB",
            asset_type=AssetCategoryType.BROKERAGE,
            manual_amount=Decimal("500.0000"),
            is_investment=True,
            created_by_user_id=str(owner_id),
        )
        owner_non_investment_category = asset_categories.create(
            name="Owner Metal Reserve",
            scope_type=AssetCategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            currency="RUB",
            asset_type=AssetCategoryType.METAL,
            manual_amount=Decimal("300.0000"),
            is_investment=False,
            created_by_user_id=str(owner_id),
        )
        owner_category = categories.create(
            name="Owner Groceries",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            icon_key="cart",
            color="#336699",
            created_by_user_id=str(owner_id),
        )
        income_category = categories.create(
            name="Owner Salary Category",
            type=CategoryType.INCOME,
            scope=CategoryScope.PERSONAL,
            owner_user_id=str(owner_id),
            household_id=None,
            icon_key="wallet",
            color="#335577",
            created_by_user_id=str(owner_id),
        )
        shared_category = categories.create(
            name="Shared Rent",
            type=CategoryType.EXPENSE,
            scope=CategoryScope.HOUSEHOLD,
            owner_user_id=None,
            household_id=str(household_id),
            icon_key="home",
            color="#445566",
            created_by_user_id=str(owner_id),
        )
        session.execute(
            update(Account)
            .where(Account.id == UUID(str(owner_asset_account.id)))
            .values(
                asset_category_id=UUID(str(owner_investment_category.id)),
                updated_at=BASE_TIME,
            )
        )
        session.flush()

    try:
        yield {
            "engine": engine,
            "owner": _actor(owner_id, ((household_id, MembershipStatus.ACTIVE),)),
            "member": _actor(member_id, ((household_id, MembershipStatus.ACTIVE),)),
            "other": _actor(other_id, ((other_household_id, MembershipStatus.ACTIVE),)),
            "invited": _actor(invited_id, ((household_id, MembershipStatus.INVITED),)),
            "former": _actor(former_id, ((household_id, MembershipStatus.LEFT),)),
            "household_id": str(household_id),
            "owner_account_id": owner_account.id,
            "owner_asset_account_id": owner_asset_account.id,
            "member_account_id": member_account.id,
            "shared_account_id": shared_account.id,
            "usd_account_id": usd_account.id,
            "owner_investment_category_id": owner_investment_category.id,
            "owner_non_investment_category_id": owner_non_investment_category.id,
            "owner_category_id": owner_category.id,
            "income_category_id": income_category.id,
            "shared_category_id": shared_category.id,
        }
    finally:
        engine.dispose()
        get_settings.cache_clear()
        sync_engine_for_url.cache_clear()


def test_personal_plan_totals_confirm_copy_and_attention(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2026-06", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": "1000.0000",
                "source": "Salary",
                "description": "main salary",
                "dayOfMonth": 31,
            },
        )
        category_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["owner_category_id"],
                "allocationMode": "amount",
                "allocationValue": "250.0000",
                "comment": "food envelope",
            },
        )
        account_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "account",
                "targetId": planning_graph["owner_account_id"],
                "allocationMode": "percent",
                "allocationValue": "80.0000",
            },
        )
        wrong_currency_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "account",
                "targetId": planning_graph["usd_account_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )
        income_category_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["income_category_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )

    assert income.status_code == 201, income.text
    assert income.json()["data"]["dayOfMonth"] == 31
    assert income.json()["data"]["effectiveDate"] == "2026-06-30"
    assert category_allocation.status_code == 201, category_allocation.text
    assert account_allocation.status_code == 201, account_allocation.text
    assert wrong_currency_allocation.status_code == 404
    assert income_category_allocation.status_code == 404

    engine = planning_graph["engine"]
    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        before = session.execute(select(func.count()).select_from(Transaction)).scalar_one()
    with _client_for_actor(owner) as client:
        confirmed = client.post(
            f"/api/v1/planning/income-sources/{income.json()['data']['id']}/confirm"
        )
        fetched = client.get(f"/api/v1/planning/plans/{plan_id}")
        history = client.get("/api/v1/planning/plans/history", params={"scope": "personal"})

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        after = session.execute(select(func.count()).select_from(Transaction)).scalar_one()

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["confirmationState"] == "confirmed"
    assert before == after == 0
    assert fetched.status_code == 200, fetched.text
    summary = fetched.json()["data"]["summary"]
    assert summary["totalPlannedIncome"] == "1000.0000"
    assert summary["totalConfirmedIncome"] == "1000.0000"
    assert summary["totalAllocatedAmount"] == "1050.0000"
    assert summary["underallocated"] is False
    assert summary["overallocated"] is True
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["items"]] == [plan_id]

    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.execute(
            update(Category)
            .where(Category.id == UUID(str(planning_graph["owner_category_id"])))
            .values(record_status="deleted", updated_at=BASE_TIME)
        )
        session.flush()

    with _client_for_actor(owner) as client:
        copied = client.post(
            f"/api/v1/planning/plans/{plan_id}/copy",
            json={"targetMonth": "2026-07"},
        )

    assert copied.status_code == 201, copied.text
    copied_data = copied.json()["data"]
    assert copied_data["month"] == "2026-07"
    assert copied_data["incomeSources"][0]["confirmationState"] == "planned"
    copied_allocations = copied_data["allocations"]
    attention_rows = [item for item in copied_allocations if item["requiresAttention"]]
    assert len(attention_rows) == 1
    assert attention_rows[0]["targetId"] is None
    assert attention_rows[0]["attentionReason"] == "TARGET_MISSING_OR_INACCESSIBLE"
    assert attention_rows[0]["targetSnapshot"]["name"] == "Owner Groceries"
    assert {item["allocationMode"] for item in copied_allocations} == {"amount", "percent"}
    assert {item["allocationValue"] for item in copied_allocations} == {
        "250.0000",
        "80.0000",
    }


def test_asset_target_uses_account_backing_summary_and_copy_attention(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2026-12", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": "1000.0000",
                "source": "Salary",
                "dayOfMonth": 15,
            },
        )
        asset_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "asset",
                "targetId": planning_graph["owner_asset_account_id"],
                "allocationMode": "amount",
                "allocationValue": "400.0000",
            },
        )
        wrong_currency_asset = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "asset",
                "targetId": planning_graph["usd_account_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )
        cash_as_asset = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "asset",
                "targetId": planning_graph["owner_account_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )
        fetched = client.get(f"/api/v1/planning/plans/{plan_id}")
        history = client.get("/api/v1/planning/plans/history", params={"scope": "personal"})

    assert income.status_code == 201, income.text
    assert asset_allocation.status_code == 201, asset_allocation.text
    asset_data = asset_allocation.json()["data"]
    assert asset_data["targetType"] == "asset"
    assert asset_data["targetId"] == planning_graph["owner_asset_account_id"]
    assert asset_data["targetSnapshot"]["targetType"] == "asset"
    assert asset_data["targetSnapshot"]["accountType"] == "brokerage"
    assert asset_data["calculatedAmount"] == "400.0000"
    assert wrong_currency_asset.status_code == 404
    assert cash_as_asset.status_code == 404
    assert fetched.status_code == 200, fetched.text
    summary = fetched.json()["data"]["summary"]
    assert summary["totalAllocatedAmount"] == "400.0000"
    assert summary["unallocatedAmount"] == "600.0000"
    assert summary["underallocated"] is True
    assert summary["overallocated"] is False
    assert history.status_code == 200, history.text
    assert plan_id in {item["id"] for item in history.json()["items"]}

    engine = planning_graph["engine"]
    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.execute(
            update(Account)
            .where(Account.id == UUID(str(planning_graph["owner_asset_account_id"])))
            .values(record_status="deleted", updated_at=BASE_TIME)
        )
        session.flush()

    with _client_for_actor(owner) as client:
        copied = client.post(
            f"/api/v1/planning/plans/{plan_id}/copy",
            json={"targetMonth": "2027-01"},
        )

    assert copied.status_code == 201, copied.text
    copied_allocation = copied.json()["data"]["allocations"][0]
    assert copied_allocation["targetType"] == "asset"
    assert copied_allocation["targetId"] is None
    assert copied_allocation["requiresAttention"] is True
    assert copied_allocation["attentionReason"] == "TARGET_MISSING_OR_INACCESSIBLE"
    assert copied_allocation["targetSnapshot"]["targetType"] == "asset"
    assert copied_allocation["targetSnapshot"]["accountType"] == "brokerage"


def test_investment_asset_category_target_validates_active_investment_category(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2027-02", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={"amount": "1000.0000", "source": "Salary", "dayOfMonth": 15},
        )
        investment_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "investment_asset_category",
                "targetId": planning_graph["owner_investment_category_id"],
                "allocationMode": "amount",
                "allocationValue": "350.0000",
            },
        )
        non_investment_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "investment_asset_category",
                "targetId": planning_graph["owner_non_investment_category_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )

    assert income.status_code == 201, income.text
    assert investment_allocation.status_code == 201, investment_allocation.text
    data = investment_allocation.json()["data"]
    assert data["targetType"] == "investment_asset_category"
    assert data["targetSnapshot"]["targetType"] == "investment_asset_category"
    assert data["targetSnapshot"]["assetType"] == "brokerage"
    assert data["calculatedAmount"] == "350.0000"
    assert non_investment_allocation.status_code == 404


def test_allocation_recurrence_and_savings_goal_contract(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2027-03-01", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        created_goal = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "investment_asset_category",
                "targetId": planning_graph["owner_investment_category_id"],
                "allocationMode": "amount",
                "allocationValue": "100.0000",
                "recurrenceType": "one_off",
                "isSavingsGoal": True,
                "goalTargetAmount": "900.0000",
                "goalDueMonth": "2027-05-01",
            },
        )
        rejected_expense_goal = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["owner_category_id"],
                "allocationMode": "amount",
                "allocationValue": "50.0000",
                "isSavingsGoal": True,
            },
        )

    assert created_goal.status_code == 201, created_goal.text
    goal_data = created_goal.json()["data"]
    assert goal_data["recurrenceType"] == "one_off"
    assert goal_data["isSavingsGoal"] is True
    assert goal_data["goalTargetAmount"] == "900.0000"
    assert goal_data["goalDueMonth"] == "2027-05"
    assert goal_data["goalMonthlyAmount"] == "300.0000"
    assert goal_data["status"] == "needs_attention"
    assert goal_data["attentionReason"] == "INVESTMENT_UNDER_PLAN"
    assert rejected_expense_goal.status_code == 422

    with _client_for_actor(owner) as client:
        updated_goal = client.patch(
            f"/api/v1/planning/allocations/{goal_data['id']}",
            json={
                "recurrenceType": "regular",
                "goalTargetAmount": "1200.0000",
                "goalDueMonth": "2027-06",
                "version": goal_data["version"],
            },
        )

    assert updated_goal.status_code == 200, updated_goal.text
    updated_data = updated_goal.json()["data"]
    assert updated_data["recurrenceType"] == "regular"
    assert updated_data["goalTargetAmount"] == "1200.0000"
    assert updated_data["goalDueMonth"] == "2027-06"
    assert updated_data["goalMonthlyAmount"] == "300.0000"


def test_actual_progress_attention_rules_and_previous_month_surplus(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        previous_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2027-04", "currency": "RUB"},
        )
        assert previous_plan.status_code == 201, previous_plan.text
        previous_plan_id = previous_plan.json()["data"]["id"]
        previous_expense = client.post(
            f"/api/v1/planning/plans/{previous_plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["owner_category_id"],
                "allocationMode": "amount",
                "allocationValue": "500.0000",
            },
        )
        assert previous_expense.status_code == 201, previous_expense.text

        current_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2027-05", "currency": "RUB"},
        )
        assert current_plan.status_code == 201, current_plan.text
        current_plan_id = current_plan.json()["data"]["id"]
        current_expense = client.post(
            f"/api/v1/planning/plans/{current_plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["owner_category_id"],
                "allocationMode": "amount",
                "allocationValue": "100.0000",
            },
        )
        current_investment = client.post(
            f"/api/v1/planning/plans/{current_plan_id}/allocations",
            json={
                "targetType": "investment_asset_category",
                "targetId": planning_graph["owner_investment_category_id"],
                "allocationMode": "amount",
                "allocationValue": "300.0000",
            },
        )
        assert current_expense.status_code == 201, current_expense.text
        assert current_investment.status_code == 201, current_investment.text

    engine = planning_graph["engine"]
    owner_id = UUID(owner.user_id or "")
    with engine.begin() as connection:
        session = Session(bind=connection, expire_on_commit=False, future=True)
        session.add_all(
            [
                Transaction(
                    id=uuid4(),
                    transaction_type="expense",
                    account_id=UUID(str(planning_graph["owner_account_id"])),
                    counterparty_account_id=None,
                    category_id=UUID(str(planning_graph["owner_category_id"])),
                    amount=Decimal("350.0000"),
                    currency="RUB",
                    occurred_at=datetime(2027, 4, 15, 12, 0, tzinfo=UTC),
                    transaction_date=datetime(2027, 4, 15, 12, 0, tzinfo=UTC).date(),
                    description="April groceries",
                    source_type="manual",
                    transfer_scope=None,
                    transfer_status=None,
                    record_status="active",
                    created_by_user_id=owner_id,
                    last_edited_by_user_id=owner_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                Transaction(
                    id=uuid4(),
                    transaction_type="expense",
                    account_id=UUID(str(planning_graph["owner_account_id"])),
                    counterparty_account_id=None,
                    category_id=UUID(str(planning_graph["owner_category_id"])),
                    amount=Decimal("120.0000"),
                    currency="RUB",
                    occurred_at=datetime(2027, 5, 10, 12, 0, tzinfo=UTC),
                    transaction_date=datetime(2027, 5, 10, 12, 0, tzinfo=UTC).date(),
                    description="May groceries",
                    source_type="manual",
                    transfer_scope=None,
                    transfer_status=None,
                    record_status="active",
                    created_by_user_id=owner_id,
                    last_edited_by_user_id=owner_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
                Transaction(
                    id=uuid4(),
                    transaction_type="asset_buy",
                    account_id=UUID(str(planning_graph["owner_asset_account_id"])),
                    counterparty_account_id=None,
                    category_id=None,
                    amount=Decimal("100.0000"),
                    currency="RUB",
                    occurred_at=datetime(2027, 5, 20, 12, 0, tzinfo=UTC),
                    transaction_date=datetime(2027, 5, 20, 12, 0, tzinfo=UTC).date(),
                    description="May investment",
                    source_type="manual",
                    transfer_scope=None,
                    transfer_status=None,
                    record_status="active",
                    created_by_user_id=owner_id,
                    last_edited_by_user_id=owner_id,
                    created_at=BASE_TIME,
                    updated_at=BASE_TIME,
                    version=1,
                ),
            ]
        )
        session.flush()

    with _client_for_actor(owner) as client:
        fetched = client.get(f"/api/v1/planning/plans/{current_plan_id}")

    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["summary"]["previousMonthSurplus"] == "150.0000"
    allocations_by_type = {item["targetType"]: item for item in data["allocations"]}
    expense = allocations_by_type["expense_category"]
    investment = allocations_by_type["investment_asset_category"]
    assert expense["actualAmount"] == "120.0000"
    assert expense["varianceAmount"] == "20.0000"
    assert expense["requiresAttention"] is True
    assert expense["status"] == "needs_attention"
    assert expense["attentionReason"] == "EXPENSE_OVER_PLAN"
    assert investment["actualAmount"] == "100.0000"
    assert investment["varianceAmount"] == "-200.0000"
    assert investment["requiresAttention"] is True
    assert investment["status"] == "needs_attention"
    assert investment["attentionReason"] == "INVESTMENT_UNDER_PLAN"


@pytest.mark.parametrize("bad_amount", ["0.0000", "-1.0000"])
def test_income_source_rejects_non_positive_amount_before_db_flush(
    planning_graph: dict[str, Any],
    bad_amount: str,
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2026-11", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        created_income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": "1000.0000",
                "source": "Salary",
                "dayOfMonth": 15,
            },
        )
        assert created_income.status_code == 201, created_income.text

        rejected_create = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": bad_amount,
                "source": "Invalid salary",
                "dayOfMonth": 15,
            },
        )
        rejected_update = client.patch(
            f"/api/v1/planning/income-sources/{created_income.json()['data']['id']}",
            json={
                "amount": bad_amount,
                "version": created_income.json()["data"]["version"],
            },
        )

    assert rejected_create.status_code == 422, rejected_create.text
    assert rejected_update.status_code == 422, rejected_update.text


def test_planning_child_delete_soft_deletes_and_hides_from_plan_view(
    planning_graph: dict[str, Any],
) -> None:
    owner = planning_graph["owner"]

    with _client_for_actor(owner) as client:
        created_plan = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2026-12", "currency": "RUB"},
        )
        assert created_plan.status_code == 201, created_plan.text
        plan_id = created_plan.json()["data"]["id"]

        created_income = client.post(
            f"/api/v1/planning/plans/{plan_id}/income-sources",
            json={
                "amount": "1000.0000",
                "source": "Salary",
                "dayOfMonth": 15,
            },
        )
        created_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["owner_category_id"],
                "allocationMode": "amount",
                "allocationValue": "250.0000",
            },
        )
        assert created_income.status_code == 201, created_income.text
        assert created_allocation.status_code == 201, created_allocation.text
        income_id = created_income.json()["data"]["id"]
        allocation_id = created_allocation.json()["data"]["id"]

        deleted_income = client.delete(f"/api/v1/planning/income-sources/{income_id}")
        deleted_allocation = client.delete(f"/api/v1/planning/allocations/{allocation_id}")
        fetched = client.get(f"/api/v1/planning/plans/{plan_id}")

    assert deleted_income.status_code == 204, deleted_income.text
    assert deleted_allocation.status_code == 204, deleted_allocation.text
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["incomeSources"] == []
    assert data["allocations"] == []
    assert data["summary"]["totalPlannedIncome"] == "0.0000"

    with Session(planning_graph["engine"], expire_on_commit=False, future=True) as session:
        income = session.get(PlanningIncomeSource, UUID(income_id))
        allocation = session.get(PlanningAllocation, UUID(allocation_id))
        assert income is not None
        assert allocation is not None
        assert income.record_status == "deleted"
        assert allocation.record_status == "deleted"
        assert income.deleted_at is not None
        assert allocation.deleted_at is not None
        assert int(income.version) == 2
        assert int(allocation.version) == 2


def test_shared_plan_authz_and_inactive_member_denials(planning_graph: dict[str, Any]) -> None:
    owner = planning_graph["owner"]
    member = planning_graph["member"]
    other = planning_graph["other"]
    invited = planning_graph["invited"]
    former = planning_graph["former"]
    household_id = planning_graph["household_id"]

    with _client_for_actor(owner) as client:
        created = client.post(
            "/api/v1/planning/plans",
            json={
                "scope": "household",
                "householdId": household_id,
                "month": "2026-08",
                "currency": "RUB",
            },
        )
        assert created.status_code == 201, created.text
        plan_id = created.json()["data"]["id"]
        shared_allocation = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "expense_category",
                "targetId": planning_graph["shared_category_id"],
                "allocationMode": "amount",
                "allocationValue": "500.0000",
            },
        )

    assert shared_allocation.status_code == 201, shared_allocation.text

    with _client_for_actor(member) as client:
        member_get = client.get(f"/api/v1/planning/plans/{plan_id}")
        member_scope_get = client.get(
            "/api/v1/planning/plans",
            params={"scope": "household", "householdId": household_id, "month": "2026-08"},
        )
        member_bad_personal_target = client.post(
            f"/api/v1/planning/plans/{plan_id}/allocations",
            json={
                "targetType": "account",
                "targetId": planning_graph["member_account_id"],
                "allocationMode": "amount",
                "allocationValue": "1.0000",
            },
        )

    assert member_get.status_code == 200
    assert member_scope_get.status_code == 200
    assert member_bad_personal_target.status_code == 404

    for actor in (other, invited, former):
        with _client_for_actor(actor) as client:
            hidden = client.get(f"/api/v1/planning/plans/{plan_id}")
            create_denied = client.post(
                "/api/v1/planning/plans",
                json={
                    "scope": "household",
                    "householdId": household_id,
                    "month": "2026-09",
                    "currency": "RUB",
                },
            )
        assert hidden.status_code == 404
        assert create_denied.status_code == 404
        assert plan_id not in hidden.text


def test_personal_other_user_forbidden(planning_graph: dict[str, Any]) -> None:
    owner = planning_graph["owner"]
    member = planning_graph["member"]

    with _client_for_actor(owner) as client:
        created = client.post(
            "/api/v1/planning/plans",
            json={"scope": "personal", "month": "2026-10", "currency": "RUB"},
        )
        assert created.status_code == 201, created.text
        plan_id = created.json()["data"]["id"]

    with _client_for_actor(member) as client:
        hidden = client.get(f"/api/v1/planning/plans/{plan_id}")
        missing = client.get(f"/api/v1/planning/plans/{uuid4()}")

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["error"]["code"] == missing.json()["error"]["code"]
    assert plan_id not in hidden.text
