from __future__ import annotations

from typing import Any
from uuid import uuid4

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


def _drilldown_ids(body: dict[str, Any]) -> set[str]:
    return {item["id"] for item in body["data"]["items"]}


def _account_ids(body: dict[str, Any]) -> set[str]:
    return {item["accountId"] for item in body["data"]["items"]}


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
