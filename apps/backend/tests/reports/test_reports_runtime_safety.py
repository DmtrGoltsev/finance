from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.config import get_settings
from app.db.models import AccountBalanceSnapshot
from app.db.session import sync_session_scope
from tests.transactions.test_transactions_db_runtime import (
    _assert_no_hidden_markers,
    _assert_same_public_error,
    _client_for_actor,
)
from tests.transactions.test_transactions_db_runtime import (
    transaction_graph as _transaction_graph_fixture,
)

transaction_graph = _transaction_graph_fixture

REPORT_ENDPOINTS = (
    "/api/v1/reports/summary",
    "/api/v1/reports/category-breakdown",
    "/api/v1/reports/account-balances",
    "/api/v1/reports/cash-flow",
    "/api/v1/reports/transactions",
)


def _params(graph: dict[str, Any], mode: str) -> dict[str, str]:
    return {
        "reportMode": mode,
        "householdId": graph["households"]["hh_ab"],
        "startDate": "2026-05-01",
        "endDate": "2026-05-31",
        "timezone": "Europe/Moscow",
    }


def _summary_by_currency(body: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        item["currency"]: item
        for item in body["data"]["totalsByCurrency"]
    }


def _summary_investments_total(body: dict[str, Any], currency: str) -> str:
    return _summary_by_currency(body).get(
        currency,
        {"investmentsTotal": "0.0000"},
    )["investmentsTotal"]


def _drilldown_ids(body: dict[str, Any]) -> set[str]:
    return {item["id"] for item in body["data"]["items"]}


def _account_ids(body: dict[str, Any]) -> set[str]:
    return {item["accountId"] for item in body["data"]["items"]}


def _expenses_by_category(body: dict[str, Any]) -> list[dict[str, Any]]:
    return body["data"]["expensesByCategory"]


def _account_item(body: dict[str, Any], account_id: str) -> dict[str, Any]:
    for item in body["data"]["items"]:
        if item["accountId"] == account_id:
            return item
    raise AssertionError(f"account not present in response: {account_id}")


def _insert_balance_snapshot(
    *,
    account_id: str,
    snapshot_date: date,
    balance: str,
    currency: str = "RUB",
) -> None:
    observed_at = datetime(
        snapshot_date.year,
        snapshot_date.month,
        snapshot_date.day,
        12,
        tzinfo=UTC,
    )
    with sync_session_scope(get_settings()) as session:
        session.add(
            AccountBalanceSnapshot(
                id=uuid4(),
                account_id=UUID(account_id),
                snapshot_date=snapshot_date,
                balance_amount=Decimal(balance),
                currency=currency,
                created_at=observed_at,
                updated_at=observed_at,
                version=1,
            )
        )


def _assert_report_response_has_no_hidden_signals(response: Any, *hidden_values: str) -> None:
    _assert_no_hidden_markers(response.text)
    assert "includedAccountIds" not in response.text
    assert "preFilterCount" not in response.text
    assert "filteredOutCount" not in response.text
    for value in hidden_values:
        assert value not in response.text


def test_shared_family_report_filters_visible_rows_before_aggregation(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    member_personal = transaction_graph["transactions"]["txn_b_expense_may"]
    owner_personal = transaction_graph["transactions"]["txn_a_income_may"]
    shared_ids = {
        transaction_graph["transactions"]["txn_ab_income_may"],
        transaction_graph["transactions"]["txn_ab_expense_may"],
    }

    with _client_for_actor(owner) as client:
        summary = client.get(
            "/api/v1/reports/summary",
            params=_params(transaction_graph, "shared_family_report"),
        )
        balances = client.get(
            "/api/v1/reports/account-balances",
            params=_params(transaction_graph, "shared_family_report"),
        )
        drilldown = client.get(
            "/api/v1/reports/transactions",
            params=_params(transaction_graph, "shared_family_report"),
        )

    assert summary.status_code == balances.status_code == drilldown.status_code == 200
    rub = _summary_by_currency(summary.json())["RUB"]
    assert rub["incomeTotal"] == "15.0000"
    assert rub["expenseTotal"] == "16.0000"
    assert rub["netTotal"] == "-1.0000"
    assert _drilldown_ids(drilldown.json()) == shared_ids
    assert _account_ids(balances.json()) == {
        transaction_graph["accounts"]["acc_ab_cash"],
        transaction_graph["accounts"]["acc_ab_savings"],
        transaction_graph["accounts"]["acc_ab_usd"],
    }
    _assert_report_response_has_no_hidden_signals(summary, member_personal, owner_personal)
    _assert_report_response_has_no_hidden_signals(drilldown, member_personal, owner_personal)


def test_combined_viewer_overview_includes_only_current_viewer_personal_rows(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    member = transaction_graph["actors"]["member_b"]
    owner_params = _params(transaction_graph, "combined_viewer_overview")
    member_personal = transaction_graph["transactions"]["txn_b_income_may"]
    owner_personal = transaction_graph["transactions"]["txn_a_income_may"]

    with _client_for_actor(owner) as client:
        owner_summary = client.get("/api/v1/reports/summary", params=owner_params)
        owner_drilldown = client.get("/api/v1/reports/transactions", params=owner_params)

    with _client_for_actor(member) as client:
        member_summary = client.get("/api/v1/reports/summary", params=owner_params)
        member_drilldown = client.get("/api/v1/reports/transactions", params=owner_params)

    assert owner_summary.status_code == member_summary.status_code == 200
    assert owner_drilldown.status_code == member_drilldown.status_code == 200
    owner_rub = _summary_by_currency(owner_summary.json())["RUB"]
    member_rub = _summary_by_currency(member_summary.json())["RUB"]
    assert owner_rub["incomeTotal"] == "26.0000"
    assert owner_rub["expenseTotal"] == "28.0000"
    assert member_rub["incomeTotal"] == "28.0000"
    assert member_rub["expenseTotal"] == "30.0000"
    assert member_personal not in owner_drilldown.text
    assert owner_personal not in member_drilldown.text
    _assert_report_response_has_no_hidden_signals(owner_summary, member_personal)
    _assert_report_response_has_no_hidden_signals(member_summary, owner_personal)


def test_report_breakdown_cash_flow_and_detail_drilldown_are_visible_only(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = _params(transaction_graph, "shared_family_report")

    with _client_for_actor(owner) as client:
        breakdown = client.get("/api/v1/reports/category-breakdown", params=params)
        cash_flow = client.get("/api/v1/reports/cash-flow", params={**params, "bucket": "month"})
        drilldown = client.get("/api/v1/reports/transactions", params=params)
        detail_responses = [
            client.get(f"/api/v1/transactions/{transaction_id}")
            for transaction_id in _drilldown_ids(drilldown.json())
        ]

    assert breakdown.status_code == cash_flow.status_code == drilldown.status_code == 200
    assert [item["transactionCount"] for item in breakdown.json()["data"]["items"]] == [1, 1]
    assert len(cash_flow.json()["data"]["points"]) == 1
    assert {response.status_code for response in detail_responses} == {200}
    _assert_report_response_has_no_hidden_signals(breakdown)
    _assert_report_response_has_no_hidden_signals(cash_flow)


def test_monthly_expense_category_aggregation_uses_date_only_boundaries(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = _params(transaction_graph, "shared_family_report")
    account_id = transaction_graph["accounts"]["acc_ab_cash"]
    category_id = transaction_graph["categories"]["cat_ab_groceries"]

    with _client_for_actor(owner) as client:
        first = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "5.0000",
                "currency": "RUB",
                "transactionDate": "2026-05-01",
                "sourceType": "manual",
            },
        )
        second = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "7.0000",
                "currency": "RUB",
                "transactionDate": "2026-05-31",
                "sourceType": "manual",
            },
        )
        outside = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "99.0000",
                "currency": "RUB",
                "transactionDate": "2026-06-01",
                "sourceType": "manual",
            },
        )
        breakdown = client.get("/api/v1/reports/category-breakdown", params=params)
        cash_flow = client.get("/api/v1/reports/cash-flow", params={**params, "bucket": "month"})

    assert first.status_code == second.status_code == outside.status_code == 201
    assert breakdown.status_code == 200, breakdown.text
    [row] = _expenses_by_category(breakdown.json())
    assert row["categoryId"] == category_id
    assert row["amount"] == "28.0000"
    assert row["transactionCount"] == 3
    assert cash_flow.status_code == 200, cash_flow.text
    [point] = cash_flow.json()["data"]["points"]
    assert point["periodStartDate"] == "2026-05-01"
    assert point["periodEndDate"] == "2026-05-31"
    assert point["totalsByCurrency"][0]["expenseTotal"] == "28.0000"


def test_monthly_reports_aggregate_repeated_expenses_across_multiple_months(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    account_id = transaction_graph["accounts"]["acc_ab_cash"]
    category_id = transaction_graph["categories"]["cat_ab_groceries"]
    base_params = {
        "reportMode": "shared_family_report",
        "householdId": transaction_graph["households"]["hh_ab"],
        "timezone": "Europe/Moscow",
    }

    with _client_for_actor(owner) as client:
        january_first = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "5.0000",
                "currency": "RUB",
                "transactionDate": "2026-01-05",
                "sourceType": "manual",
            },
        )
        january_second = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "7.0000",
                "currency": "RUB",
                "transactionDate": "2026-01-31",
                "sourceType": "manual",
            },
        )
        february = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "expense",
                "accountId": account_id,
                "categoryId": category_id,
                "amount": "11.0000",
                "currency": "RUB",
                "transactionDate": "2026-02-01",
                "sourceType": "manual",
            },
        )
        january_breakdown = client.get(
            "/api/v1/reports/category-breakdown",
            params={
                **base_params,
                "startDate": "2026-01-01",
                "endDate": "2026-01-31",
            },
        )
        cash_flow = client.get(
            "/api/v1/reports/cash-flow",
            params={
                **base_params,
                "startDate": "2026-01-01",
                "endDate": "2026-02-28",
                "bucket": "month",
            },
        )

    assert january_first.status_code == 201, january_first.text
    assert january_second.status_code == 201, january_second.text
    assert february.status_code == 201, february.text
    assert january_breakdown.status_code == 200, january_breakdown.text
    [january_row] = _expenses_by_category(january_breakdown.json())
    assert january_row["categoryId"] == category_id
    assert january_row["amount"] == "12.0000"
    assert january_row["transactionCount"] == 2

    assert cash_flow.status_code == 200, cash_flow.text
    points_by_start = {
        point["periodStartDate"]: point for point in cash_flow.json()["data"]["points"]
    }
    assert points_by_start["2026-01-01"]["periodEndDate"] == "2026-01-31"
    assert points_by_start["2026-01-01"]["totalsByCurrency"][0]["expenseTotal"] == "12.0000"
    assert points_by_start["2026-02-01"]["periodEndDate"] == "2026-02-28"
    assert points_by_start["2026-02-01"]["totalsByCurrency"][0]["expenseTotal"] == "11.0000"


def test_report_totals_keep_transfers_and_asset_ops_out_of_spending(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = _params(transaction_graph, "shared_family_report")

    with _client_for_actor(owner) as client:
        transfer = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "transfer",
                "accountId": transaction_graph["accounts"]["acc_ab_cash"],
                "counterpartyAccountId": transaction_graph["accounts"]["acc_ab_savings"],
                "amount": "3.0000",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:00:00+00:00",
                "sourceType": "manual",
            },
        )
        asset_buy = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "asset_buy",
                "accountId": transaction_graph["accounts"]["acc_ab_savings"],
                "amount": "4.0000",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:15:00+00:00",
                "sourceType": "manual",
            },
        )
        summary = client.get("/api/v1/reports/summary", params=params)
        breakdown = client.get("/api/v1/reports/category-breakdown", params=params)

    assert transfer.status_code == 201
    assert asset_buy.status_code == 201
    assert summary.status_code == 200
    rub = _summary_by_currency(summary.json())["RUB"]
    assert rub["incomeTotal"] == "15.0000"
    assert rub["expenseTotal"] == "16.0000"
    assert rub["transferTotal"] == "3.0000"
    assert rub["netCashFlow"] == "-1.0000"
    assert rub["netTotal"] == "-1.0000"
    assert {
        item["categoryType"]
        for item in breakdown.json()["data"]["expensesByCategory"]
    } == {"expense"}


def test_summary_investments_total_uses_monthly_transfers_into_investment_accounts(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    base_params = {
        "reportMode": "shared_family_report",
        "householdId": transaction_graph["households"]["hh_ab"],
        "timezone": "Europe/Moscow",
    }
    july_params = {
        **base_params,
        "startDate": "2026-07-01",
        "endDate": "2026-07-31",
    }
    june_params = {
        **base_params,
        "startDate": "2026-06-01",
        "endDate": "2026-06-30",
    }

    with _client_for_actor(owner) as client:
        category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "July Shared Investments",
                "scopeType": "household",
                "householdId": transaction_graph["households"]["hh_ab"],
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "0.0000",
                "isInvestment": True,
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["data"]["id"]

        linked = client.patch(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_ab_savings']}",
            json={"assetCategoryId": category_id},
        )
        july_before_transfer = client.get("/api/v1/reports/summary", params=july_params)
        ordinary_account = client.post(
            "/api/v1/accounts",
            json={
                "name": "Shared RUB Ordinary",
                "accountType": "cash",
                "ownershipType": "shared",
                "householdId": transaction_graph["households"]["hh_ab"],
                "currency": "RUB",
                "initialBalance": "100.0000",
            },
        )
        assert ordinary_account.status_code == 201, ordinary_account.text
        ordinary_account_id = ordinary_account.json()["data"]["id"]

        july_investment_transfer = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "transfer",
                "accountId": transaction_graph["accounts"]["acc_ab_cash"],
                "counterpartyAccountId": transaction_graph["accounts"]["acc_ab_savings"],
                "amount": "40.0000",
                "currency": "RUB",
                "transactionDate": "2026-07-10",
                "sourceType": "manual",
            },
        )
        july_ordinary_transfer = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "transfer",
                "accountId": transaction_graph["accounts"]["acc_ab_savings"],
                "counterpartyAccountId": ordinary_account_id,
                "amount": "7.0000",
                "currency": "RUB",
                "transactionDate": "2026-07-11",
                "sourceType": "manual",
            },
        )
        july_summary = client.get("/api/v1/reports/summary", params=july_params)
        june_summary = client.get("/api/v1/reports/summary", params=june_params)

    assert linked.status_code == 200, linked.text
    assert july_before_transfer.status_code == 200, july_before_transfer.text
    assert _summary_investments_total(july_before_transfer.json(), "RUB") == "0.0000"
    assert july_investment_transfer.status_code == 201, july_investment_transfer.text
    assert july_ordinary_transfer.status_code == 201, july_ordinary_transfer.text
    assert july_summary.status_code == 200, july_summary.text
    assert june_summary.status_code == 200, june_summary.text

    july_rub = _summary_by_currency(july_summary.json())["RUB"]
    assert july_rub["transferTotal"] == "47.0000"
    assert july_rub["investmentsTotal"] == "40.0000"
    assert _summary_investments_total(june_summary.json(), "RUB") == "0.0000"


def test_account_balances_include_asset_categories_manual_amount_and_investments(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = _params(transaction_graph, "shared_family_report")

    with _client_for_actor(owner) as client:
        category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Shared Investments",
                "scopeType": "household",
                "householdId": transaction_graph["households"]["hh_ab"],
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "100.0000",
                "isInvestment": True,
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["data"]["id"]

        linked = client.patch(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_ab_savings']}",
            json={"assetCategoryId": category_id},
        )
        before_delete = client.get("/api/v1/reports/account-balances", params=params)
        summary = client.get("/api/v1/reports/summary", params=params)
        changed_balance = client.patch(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_ab_savings']}",
            json={"currentBalance": "999.0000"},
        )
        historical_after_balance_change = client.get(
            "/api/v1/reports/account-balances",
            params=params,
        )
        deleted = client.delete(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_ab_savings']}"
        )
        after_delete = client.get("/api/v1/reports/account-balances", params=params)

    assert linked.status_code == 200, linked.text
    assert before_delete.status_code == 200, before_delete.text
    group = before_delete.json()["data"]["assetCategoryGroups"][0]
    assert group["assetCategoryId"] == category_id
    assert group["manualAmount"] == "100.0000"
    assert group["accountCount"] == 1
    assert group["currentBalanceTotal"] == "200.0000"
    assert before_delete.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "200.0000"}
    ]
    assert summary.status_code == 200
    assert _summary_by_currency(summary.json())["RUB"]["investmentsTotal"] == "0.0000"
    assert changed_balance.status_code == 200, changed_balance.text
    assert historical_after_balance_change.status_code == 200
    historical_group = historical_after_balance_change.json()["data"]["assetCategoryGroups"][0]
    assert historical_group["currentBalanceTotal"] == "200.0000"
    assert historical_after_balance_change.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "200.0000"}
    ]

    assert deleted.status_code == 204
    group_after_delete = after_delete.json()["data"]["assetCategoryGroups"][0]
    assert group_after_delete["accountCount"] == 0
    assert group_after_delete["currentBalanceTotal"] == "100.0000"
    assert after_delete.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "100.0000"}
    ]
    assert transaction_graph["accounts"]["acc_ab_savings"] not in _account_ids(after_delete.json())


def test_transfer_into_linked_investment_account_updates_current_asset_category_total(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = {
        "reportMode": "shared_family_report",
        "householdId": transaction_graph["households"]["hh_ab"],
        "timezone": "Europe/Moscow",
    }

    with _client_for_actor(owner) as client:
        category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Current Shared Investments",
                "scopeType": "household",
                "householdId": transaction_graph["households"]["hh_ab"],
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "100.0000",
                "isInvestment": True,
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["data"]["id"]

        linked = client.patch(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_ab_savings']}",
            json={"assetCategoryId": category_id},
        )
        transfer = client.post(
            "/api/v1/transactions",
            json={
                "transactionType": "transfer",
                "accountId": transaction_graph["accounts"]["acc_ab_cash"],
                "counterpartyAccountId": transaction_graph["accounts"]["acc_ab_savings"],
                "amount": "25.0000",
                "currency": "RUB",
                "occurredAt": "2026-05-17T14:00:00+00:00",
                "sourceType": "manual",
            },
        )
        balances = client.get("/api/v1/reports/account-balances", params=params)

    assert linked.status_code == 200, linked.text
    assert transfer.status_code == 201, transfer.text
    assert balances.status_code == 200, balances.text
    group = balances.json()["data"]["assetCategoryGroups"][0]
    assert group["assetCategoryId"] == category_id
    assert group["linkedAccountsTotal"] == "125.0000"
    assert group["currentBalanceTotal"] == "225.0000"
    assert balances.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "225.0000"}
    ]


def test_account_balance_reports_use_historical_snapshot_dates_for_investments(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    account_id = transaction_graph["accounts"]["acc_ab_savings"]
    params = {
        "reportMode": "shared_family_report",
        "householdId": transaction_graph["households"]["hh_ab"],
        "timezone": "Europe/Moscow",
    }

    with _client_for_actor(owner) as client:
        category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Historical Investments",
                "scopeType": "household",
                "householdId": transaction_graph["households"]["hh_ab"],
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "100.0000",
                "isInvestment": True,
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["data"]["id"]

        linked = client.patch(
            f"/api/v1/accounts/{account_id}",
            json={"assetCategoryId": category_id},
        )
        assert linked.status_code == 200, linked.text

    _insert_balance_snapshot(
        account_id=account_id,
        snapshot_date=date(2026, 3, 31),
        balance="75.0000",
    )
    _insert_balance_snapshot(
        account_id=account_id,
        snapshot_date=date(2026, 4, 30),
        balance="120.0000",
    )
    _insert_balance_snapshot(
        account_id=account_id,
        snapshot_date=date(2026, 5, 31),
        balance="200.0000",
    )

    with _client_for_actor(owner) as client:
        before_april_snapshot = client.get(
            "/api/v1/reports/account-balances",
            params={**params, "startDate": "2026-04-01", "endDate": "2026-04-15"},
        )
        after_april_snapshot = client.get(
            "/api/v1/reports/account-balances",
            params={**params, "startDate": "2026-04-01", "endDate": "2026-04-30"},
        )
        may_snapshot = client.get(
            "/api/v1/reports/account-balances",
            params={**params, "startDate": "2026-05-01", "endDate": "2026-05-31"},
        )

    assert before_april_snapshot.status_code == 200, before_april_snapshot.text
    before_item = _account_item(before_april_snapshot.json(), account_id)
    assert before_item["currentBalance"] == "75.0000"
    assert before_item["balanceAsOf"] == "2026-03-31"
    assert before_april_snapshot.json()["data"]["assetCategoryGroups"][0][
        "currentBalanceTotal"
    ] == "175.0000"
    assert before_april_snapshot.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "175.0000"}
    ]

    assert after_april_snapshot.status_code == 200, after_april_snapshot.text
    after_item = _account_item(after_april_snapshot.json(), account_id)
    assert after_item["currentBalance"] == "120.0000"
    assert after_item["balanceAsOf"] == "2026-04-30"
    assert after_april_snapshot.json()["data"]["assetCategoryGroups"][0][
        "currentBalanceTotal"
    ] == "220.0000"
    assert after_april_snapshot.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "220.0000"}
    ]

    assert may_snapshot.status_code == 200, may_snapshot.text
    may_item = _account_item(may_snapshot.json(), account_id)
    assert may_item["currentBalance"] == "200.0000"
    assert may_item["balanceAsOf"] == "2026-05-31"
    assert may_snapshot.json()["data"]["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "300.0000"}
    ]


def test_personal_report_without_household_id_succeeds_for_summary_and_account_balances(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = {
        "reportMode": "personal",
        "startDate": "2026-05-01",
        "endDate": "2026-05-31",
        "timezone": "Europe/Moscow",
    }
    owner_personal_accounts = {
        transaction_graph["accounts"]["acc_a_cash"],
        transaction_graph["accounts"]["acc_a_savings"],
        transaction_graph["accounts"]["acc_a_usd"],
    }
    hidden_values = (
        transaction_graph["transactions"]["txn_ab_income_may"],
        transaction_graph["transactions"]["txn_b_income_may"],
        transaction_graph["accounts"]["acc_ab_cash"],
        transaction_graph["accounts"]["acc_b_cash"],
    )

    with _client_for_actor(owner) as client:
        category = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Personal Investments",
                "scopeType": "personal",
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "50.0000",
                "isInvestment": True,
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["data"]["id"]

        linked = client.patch(
            f"/api/v1/accounts/{transaction_graph['accounts']['acc_a_savings']}",
            json={"assetCategoryId": category_id},
        )
        summary = client.get("/api/v1/reports/summary", params=params)
        balances = client.get("/api/v1/reports/account-balances", params=params)
        explicit_household_summary = client.get(
            "/api/v1/reports/summary",
            params={**params, "householdId": transaction_graph["households"]["hh_ab"]},
        )

    assert linked.status_code == 200, linked.text
    assert summary.status_code == 200, summary.text
    assert balances.status_code == 200, balances.text
    assert explicit_household_summary.status_code == 200, explicit_household_summary.text

    summary_data = summary.json()["data"]
    balances_data = balances.json()["data"]
    explicit_household_summary_data = explicit_household_summary.json()["data"]
    assert summary_data["scope"]["reportMode"] == "personal"
    assert summary_data["scope"]["householdId"] is None
    assert balances_data["scope"]["reportMode"] == "personal"
    assert balances_data["scope"]["householdId"] is None
    assert explicit_household_summary_data["scope"]["reportMode"] == "personal"
    assert explicit_household_summary_data["scope"]["householdId"] is None

    rub = _summary_by_currency(summary.json())["RUB"]
    assert rub["incomeTotal"] == "11.0000"
    assert rub["expenseTotal"] == "12.0000"
    assert rub["investmentsTotal"] == "0.0000"
    assert _account_ids(balances.json()) == owner_personal_accounts

    group = balances_data["assetCategoryGroups"][0]
    assert group["assetCategoryId"] == category_id
    assert group["householdId"] is None
    assert group["ownerUserId"] == owner.user_id
    assert group["manualAmount"] == "50.0000"
    assert group["linkedAccountsTotal"] == "100.0000"
    assert group["currentBalanceTotal"] == "150.0000"
    assert group["isInvestment"] is True
    assert balances_data["investmentsByCurrency"] == [
        {"currency": "RUB", "investmentsTotal": "150.0000"}
    ]
    _assert_report_response_has_no_hidden_signals(summary, *hidden_values)
    _assert_report_response_has_no_hidden_signals(balances, *hidden_values)


def test_household_report_modes_still_require_household_id(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    base_params = {
        "startDate": "2026-05-01",
        "endDate": "2026-05-31",
        "timezone": "Europe/Moscow",
    }

    with _client_for_actor(owner) as client:
        responses = [
            client.get(endpoint, params={**base_params, "reportMode": mode})
            for endpoint in (
                "/api/v1/reports/summary",
                "/api/v1/reports/account-balances",
            )
            for mode in ("shared_family_report", "combined_viewer_overview")
        ]

    assert {response.status_code for response in responses} == {422}
    assert {response.json()["error"]["code"] for response in responses} == {
        "HOUSEHOLD_ID_REQUIRED"
    }


def test_non_members_invited_and_former_get_neutral_report_denials(
    transaction_graph: dict[str, Any],
) -> None:
    params = _params(transaction_graph, "combined_viewer_overview")
    missing_params = {**params, "householdId": str(uuid4())}

    for actor_label in ("other_c", "invited_ab", "former_ab"):
        actor = transaction_graph["actors"][actor_label]
        with _client_for_actor(actor) as client:
            inaccessible = client.get("/api/v1/reports/summary", params=params)
            missing = client.get("/api/v1/reports/summary", params=missing_params)

        assert inaccessible.status_code == missing.status_code == 404
        _assert_same_public_error(inaccessible, missing)
        _assert_report_response_has_no_hidden_signals(
            inaccessible,
            transaction_graph["accounts"]["acc_ab_cash"],
        )


def test_report_direct_filters_reject_hidden_and_missing_references_neutrally(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    params = _params(transaction_graph, "shared_family_report")
    hidden_member_account = transaction_graph["accounts"]["acc_b_cash"]
    hidden_owner_category = transaction_graph["categories"]["cat_a_food"]

    with _client_for_actor(owner) as client:
        hidden_account = client.get(
            "/api/v1/reports/summary",
            params={**params, "accountIds": hidden_member_account},
        )
        missing_account = client.get(
            "/api/v1/reports/summary",
            params={**params, "accountIds": str(uuid4())},
        )
        hidden_category = client.get(
            "/api/v1/reports/category-breakdown",
            params={**params, "categoryIds": hidden_owner_category},
        )
        missing_category = client.get(
            "/api/v1/reports/category-breakdown",
            params={**params, "categoryIds": str(uuid4())},
        )

    assert hidden_account.status_code == missing_account.status_code == 404
    assert hidden_category.status_code == missing_category.status_code == 404
    _assert_same_public_error(hidden_account, missing_account)
    _assert_same_public_error(hidden_category, missing_category)
    _assert_report_response_has_no_hidden_signals(hidden_account, hidden_member_account)
    _assert_report_response_has_no_hidden_signals(hidden_category, hidden_owner_category)
