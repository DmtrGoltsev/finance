from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.authz import ReportMode, SourceType, TransferScopeKind
from app.db.model_enums import SOURCE_TYPES, TRANSFER_SCOPES
from app.main import create_app
from tests.api.route_introspection import iter_api_routes

REPO_ROOT = Path(__file__).resolve().parents[4]
OPENAPI_CONTRACT_PATH = REPO_ROOT / "api" / "openapi" / "openapi.yaml"
FIXTURE_ROOT = (
    REPO_ROOT / "qa" / "fixtures" / "owner-member-other-invited-former-v1"
)
CANONICAL_GRAPH_PATH = FIXTURE_ROOT / "canonical-uuid-graph.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
IGNORED_RUNTIME_METHODS = {"HEAD", "OPTIONS"}
API_CATCH_ALL = "/api/v1/{path}"

EXPECTED_MOUNTED_TRANSACTION_OPERATIONS = frozenset(
    {
        ("GET", "/api/v1/transactions"),
        ("POST", "/api/v1/transactions"),
        ("GET", "/api/v1/transactions/autocomplete"),
        ("GET", "/api/v1/transactions/{transactionId}"),
        ("PATCH", "/api/v1/transactions/{transactionId}"),
        ("DELETE", "/api/v1/transactions/{transactionId}"),
        ("POST", "/api/v1/transactions/{transactionId}/restore"),
    }
)

EXPECTED_MOUNTED_REPORT_OPERATIONS = frozenset(
    {
        ("GET", "/api/v1/reports/summary"),
        ("GET", "/api/v1/reports/category-breakdown"),
        ("GET", "/api/v1/reports/account-balances"),
        ("GET", "/api/v1/reports/cash-flow"),
        ("GET", "/api/v1/reports/transactions"),
    }
)

EXPECTED_MOUNTED_CAPTURE_DRAFT_OPERATIONS = frozenset(
    {
        ("GET", "/api/v1/capture-drafts"),
        ("POST", "/api/v1/capture-drafts"),
        ("POST", "/api/v1/capture-drafts/screenshot-ocr"),
        ("PUT", "/api/v1/capture-drafts/category-mappings"),
        ("PATCH", "/api/v1/capture-drafts/{draftId}"),
        ("POST", "/api/v1/capture-drafts/{draftId}/confirm"),
        ("POST", "/api/v1/capture-drafts/{draftId}/discard"),
    }
)

EXPECTED_UNMOUNTED_W3_OPERATIONS = frozenset(
    {
        ("POST", "/api/v1/transactions/{transactionId}/void"),
    }
)

FORBIDDEN_TRANSFER_ROUTE_PREFIX = "/api/v1/transfers"


def _route_operations() -> set[tuple[str, str]]:
    application = create_app()
    operations: set[tuple[str, str]] = set()

    for route in iter_api_routes(application.routes):
        if route.path_format == API_CATCH_ALL:
            continue
        for method in sorted(route.methods or ()):
            if method not in IGNORED_RUNTIME_METHODS:
                operations.add((method, route.path_format))

    return operations


def _schema_block(schema_name: str) -> list[str]:
    marker = f"    {schema_name}:"
    lines = OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8").splitlines()
    block: list[str] = []
    in_block = False
    in_schemas = False

    for raw_line in lines:
        if raw_line == "  schemas:":
            in_schemas = True
            continue

        if not in_schemas:
            continue

        if in_schemas and raw_line.startswith("  ") and not raw_line.startswith("    "):
            break

        if raw_line == marker:
            in_block = True
            block.append(raw_line)
            continue

        if not in_block:
            continue

        if raw_line.startswith("    ") and not raw_line.startswith("      "):
            break

        block.append(raw_line)

    assert block, f"schema block not found: {schema_name}"
    return block


def _inline_array_value(block: list[str], key: str) -> list[str]:
    prefix = f"{key}: ["
    for raw_line in block:
        stripped = raw_line.strip()
        if stripped.startswith(prefix) and stripped.endswith("]"):
            inside = stripped.removeprefix(prefix).removesuffix("]")
            return [item.strip() for item in inside.split(",") if item.strip()]

    raise AssertionError(f"inline array not found: {key}")


def _load_canonical_graph() -> dict[str, Any]:
    return json.loads(CANONICAL_GRAPH_PATH.read_text(encoding="utf-8"))


def _assert_neutral_not_found(body: dict[str, Any], request_id: str) -> None:
    assert set(body) == {"error"}
    assert body["error"] == {
        "code": "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
        "message": "Resource not found or not accessible.",
        "requestId": request_id,
    }


def test_w3_transactions_and_reports_mounted_transfers_remain_gated() -> None:
    mounted_operations = _route_operations()

    assert EXPECTED_MOUNTED_TRANSACTION_OPERATIONS <= mounted_operations
    assert EXPECTED_MOUNTED_CAPTURE_DRAFT_OPERATIONS <= mounted_operations
    assert EXPECTED_MOUNTED_REPORT_OPERATIONS <= mounted_operations
    assert mounted_operations.isdisjoint(EXPECTED_UNMOUNTED_W3_OPERATIONS)
    assert {
        operation
        for operation in mounted_operations
        if operation[1] == FORBIDDEN_TRANSFER_ROUTE_PREFIX
        or operation[1].startswith(f"{FORBIDDEN_TRANSFER_ROUTE_PREFIX}/")
    } == set()


def test_runtime_openapi_exposes_transactions_and_reports_for_w3_runtime_workers(client) -> None:
    runtime_schema = client.get("/openapi.json").json()
    runtime_paths = set(runtime_schema["paths"])

    assert "/api/v1/transactions" in runtime_paths
    assert "/api/v1/transactions/{transactionId}" in runtime_paths
    assert "/api/v1/transactions/autocomplete" in runtime_paths
    assert "/api/v1/transactions/{transactionId}/restore" in runtime_paths
    assert "/api/v1/transactions/{transactionId}/void" not in runtime_paths
    assert "/api/v1/capture-drafts" in runtime_paths
    assert "/api/v1/capture-drafts/screenshot-ocr" in runtime_paths
    assert "/api/v1/capture-drafts/category-mappings" in runtime_paths
    assert "/api/v1/capture-drafts/{draftId}" in runtime_paths
    assert "/api/v1/capture-drafts/{draftId}/confirm" in runtime_paths
    assert "/api/v1/capture-drafts/{draftId}/discard" in runtime_paths
    assert "/api/v1/reports/summary" in runtime_paths
    assert "/api/v1/reports/category-breakdown" in runtime_paths
    assert "/api/v1/reports/account-balances" in runtime_paths
    assert "/api/v1/reports/cash-flow" in runtime_paths
    assert "/api/v1/reports/transactions" in runtime_paths
    assert not any(path.startswith(FORBIDDEN_TRANSFER_ROUTE_PREFIX) for path in runtime_paths)


def test_unmounted_w3_transfer_family_void_and_unknown_reports_return_neutral_404_envelope(
    client,
) -> None:
    request_id = "req-w3-unmounted-contract"
    responses = [
        client.get("/api/v1/reports/not-a-runtime-route", headers={"X-Request-ID": request_id}),
        client.post(
            "/api/v1/transactions/not-a-transfer/void",
            json={"description": "fixture-sentinel-must-not-echo"},
            headers={"X-Request-ID": request_id},
        ),
        client.post("/api/v1/transfers", headers={"X-Request-ID": request_id}),
    ]

    for response in responses:
        assert response.status_code == 404
        _assert_neutral_not_found(response.json(), request_id)
        assert "fixture-sentinel-must-not-echo" not in response.text


def test_w3_public_and_persistence_enum_boundaries_remain_frozen() -> None:
    graph_contracts = _load_canonical_graph()["contracts"]

    assert _inline_array_value(_schema_block("SourceType"), "enum") == ["manual"]
    assert _inline_array_value(_schema_block("ReportMode"), "enum") == [
        "personal",
        "shared_family_report",
        "combined_viewer_overview",
    ]
    assert _inline_array_value(_schema_block("TransferScope"), "enum") == [
        "personal_same_owner",
        "household_same_household",
    ]

    assert tuple(item.value for item in SourceType) == ("manual",)
    assert tuple(item.value for item in ReportMode) == (
        "personal",
        "shared_family_report",
        "combined_viewer_overview",
    )
    assert tuple(item.value for item in TransferScopeKind) == (
        "personal_same_owner",
        "household_same_household",
    )
    assert SOURCE_TYPES == ("manual",)
    assert TRANSFER_SCOPES == ("personal_same_owner", "household_same_household")
    assert graph_contracts["sourceType"] == ["manual"]
    assert graph_contracts["reportModes"] == [
        "personal",
        "shared_family_report",
        "combined_viewer_overview",
    ]
    assert graph_contracts["transferScopes"] == [
        "personal_same_owner",
        "household_same_household",
    ]


def test_w3_contract_tracks_mounted_reports_and_forbidden_transfer_family() -> None:
    graph = _load_canonical_graph()

    assert {path for _method, path in EXPECTED_MOUNTED_REPORT_OPERATIONS} == {
        "/api/v1/reports/summary",
        "/api/v1/reports/category-breakdown",
        "/api/v1/reports/account-balances",
        "/api/v1/reports/cash-flow",
        "/api/v1/reports/transactions",
    }
    assert graph["contracts"]["forbiddenRouteFamilies"] == ["/api/v1/transfers"]
