from __future__ import annotations

from typing import Any

from tests.transactions.test_transactions_db_runtime import (
    _client_for_actor,
)
from tests.transactions.test_transactions_db_runtime import (
    transaction_graph as _transaction_graph_fixture,
)

transaction_graph = _transaction_graph_fixture


def _payload(graph: dict[str, Any], *, target_scope: str = "personal") -> dict[str, Any]:
    return {
        "reportType": "bank_statement",
        "sourceType": "file_metadata_only",
        "targetScope": target_scope,
        "householdId": graph["households"]["hh_ab"] if target_scope == "shared" else None,
        "fileName": "C:\\Users\\owner\\Downloads\\statement.pdf",
        "fileSizeBytes": 245760,
        "mimeType": "application/pdf",
    }


def test_report_preview_returns_safe_placeholder_contract(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]

    with _client_for_actor(owner) as client:
        response = client.post("/api/v1/imports/report-preview", json=_payload(transaction_graph))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "preview_placeholder"
    assert body["canConfirm"] is False
    assert body["willChangeData"] is False
    assert body["scope"] == {"targetScope": "personal", "householdId": None}
    assert body["file"] == {
        "fileName": "statement.pdf",
        "fileSizeBytes": 245760,
        "mimeType": "application/pdf",
    }
    assert body["summary"]["title"] == "Предварительный просмотр импорта"
    assert body["summary"]["statusText"] == "Импорт пока не выполняется"
    assert [section["key"] for section in body["summary"]["sections"]] == [
        "accounts_assets",
        "transactions",
        "categories",
        "transfers",
        "brokerage_deposits_metals",
    ]
    assert {section["status"] for section in body["summary"]["sections"]} == {
        "not_recognized_yet"
    }
    warning_text = " ".join(warning["text"] for warning in body["warnings"])
    assert "Импорт пока не выполняется" in warning_text
    assert "Содержимое файла не сохраняется и не разбирается" in warning_text
    assert "Данные не изменятся без подтверждения" in warning_text
    assert "owner\\Downloads" not in response.text
    assert "content" not in response.text.lower()


def test_report_preview_sanitizes_file_name_without_leaking_paths_or_nul(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = {
        **_payload(transaction_graph),
        "fileName": "/Users/owner/private/brokerage\x00-report.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    with _client_for_actor(owner) as client:
        response = client.post("/api/v1/imports/report-preview", json=payload)

    assert response.status_code == 200
    assert response.json()["file"]["fileName"] == "brokerage-report.xlsx"
    assert "/Users/owner/private" not in response.text
    assert "\\u0000" not in response.text


def test_personal_report_preview_rejects_household_id(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]

    with _client_for_actor(owner) as client:
        response = client.post(
            "/api/v1/imports/report-preview",
            json={
                **_payload(transaction_graph),
                "householdId": transaction_graph["households"]["hh_ab"],
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert transaction_graph["households"]["hh_ab"] not in response.text


def test_shared_report_preview_is_allowed_for_active_member(
    transaction_graph: dict[str, Any],
) -> None:
    member = transaction_graph["actors"]["member_b"]

    with _client_for_actor(member) as client:
        response = client.post(
            "/api/v1/imports/report-preview",
            json=_payload(transaction_graph, target_scope="shared"),
        )

    assert response.status_code == 200
    assert response.json()["scope"] == {
        "targetScope": "shared",
        "householdId": transaction_graph["households"]["hh_ab"],
    }
    assert response.json()["canConfirm"] is False
    assert response.json()["willChangeData"] is False


def test_report_preview_does_not_mutate_finance_records(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = _payload(transaction_graph, target_scope="shared")

    with _client_for_actor(owner) as client:
        before_accounts = client.get("/api/v1/accounts").json()
        before_categories = client.get("/api/v1/categories").json()
        before_transactions = client.get("/api/v1/transactions").json()
        response = client.post("/api/v1/imports/report-preview", json=payload)
        after_accounts = client.get("/api/v1/accounts").json()
        after_categories = client.get("/api/v1/categories").json()
        after_transactions = client.get("/api/v1/transactions").json()

    assert response.status_code == 200
    assert after_accounts == before_accounts
    assert after_categories == before_categories
    assert after_transactions == before_transactions


def test_report_preview_rejects_content_like_fields(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]
    payload = {
        **_payload(transaction_graph),
        "base64": "c2VjcmV0LWZpbGU=",
        "rows": [{"description": "must not be accepted"}],
        "parsedData": {"accountIds": ["hidden-account"]},
    }

    with _client_for_actor(owner) as client:
        response = client.post("/api/v1/imports/report-preview", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "c2VjcmV0" not in response.text
    assert "hidden-account" not in response.text


def test_report_preview_rejects_reserved_source_type(
    transaction_graph: dict[str, Any],
) -> None:
    owner = transaction_graph["actors"]["owner_a"]

    with _client_for_actor(owner) as client:
        response = client.post(
            "/api/v1/imports/report-preview",
            json={**_payload(transaction_graph), "sourceType": "file_import"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ENUM_VALUE"


def test_shared_report_preview_requires_active_membership(
    transaction_graph: dict[str, Any],
) -> None:
    invited = transaction_graph["actors"]["invited_ab"]

    with _client_for_actor(invited) as client:
        response = client.post(
            "/api/v1/imports/report-preview",
            json=_payload(transaction_graph, target_scope="shared"),
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
    assert transaction_graph["households"]["hh_ab"] not in response.text
