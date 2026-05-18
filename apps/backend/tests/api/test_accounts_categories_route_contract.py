from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
OPENAPI_CONTRACT_PATH = REPO_ROOT / "api" / "openapi" / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
IGNORED_RUNTIME_METHODS = {"HEAD", "OPTIONS"}

EXPECTED_APPROVED_SCHEMA_OPERATIONS = {
    ("GET", "/api/v1/accounts"): "listAccounts",
    ("POST", "/api/v1/accounts"): "createAccount",
    ("GET", "/api/v1/accounts/autocomplete"): "autocompleteAccounts",
    ("GET", "/api/v1/accounts/{accountId}"): "getAccount",
    ("PATCH", "/api/v1/accounts/{accountId}"): "updateAccount",
    ("DELETE", "/api/v1/accounts/{accountId}"): "deleteAccount",
    ("POST", "/api/v1/accounts/{accountId}/archive"): "archiveAccount",
    ("POST", "/api/v1/accounts/{accountId}/restore"): "restoreAccount",
    ("GET", "/api/v1/categories"): "listCategories",
    ("POST", "/api/v1/categories"): "createCategory",
    ("GET", "/api/v1/categories/autocomplete"): "autocompleteCategories",
    ("GET", "/api/v1/categories/{categoryId}"): "getCategory",
    ("PATCH", "/api/v1/categories/{categoryId}"): "updateCategory",
    ("DELETE", "/api/v1/categories/{categoryId}"): "deleteCategory",
    ("POST", "/api/v1/categories/{categoryId}/archive"): "archiveCategory",
    ("POST", "/api/v1/categories/{categoryId}/restore"): "restoreCategory",
}

EXPECTED_APPROVED_SESSION_OPERATIONS = {
    ("POST", "/api/v1/sessions"): "createSession",
    ("GET", "/api/v1/sessions/current"): "getCurrentSession",
    ("DELETE", "/api/v1/sessions/current"): "deleteCurrentSession",
}
EXPECTED_APPROVED_TRANSACTION_OPERATIONS = {
    ("GET", "/api/v1/transactions"): "listTransactions",
    ("POST", "/api/v1/transactions"): "createTransaction",
    ("GET", "/api/v1/transactions/autocomplete"): "autocompleteTransactions",
    ("GET", "/api/v1/transactions/{transactionId}"): "getTransaction",
    ("PATCH", "/api/v1/transactions/{transactionId}"): "updateTransaction",
    ("DELETE", "/api/v1/transactions/{transactionId}"): "deleteTransaction",
    ("POST", "/api/v1/transactions/{transactionId}/restore"): "restoreTransaction",
}
EXPECTED_APPROVED_REPORT_OPERATIONS = {
    ("GET", "/api/v1/reports/summary"): "getReportSummary",
    ("GET", "/api/v1/reports/category-breakdown"): "getReportCategoryBreakdown",
    ("GET", "/api/v1/reports/account-balances"): "getReportAccountBalances",
    ("GET", "/api/v1/reports/cash-flow"): "getReportCashFlow",
    ("GET", "/api/v1/reports/transactions"): "getReportTransactions",
}
EXPECTED_APPROVED_IMPORT_OPERATIONS = {
    ("POST", "/api/v1/imports/report-preview"): "previewImportReport",
}
EXPECTED_UNMOUNTED_SESSION_OPERATIONS = frozenset(
    {
        ("DELETE", "/api/v1/sessions"),
    }
)

EXPECTED_SCHEMA_INCLUDED_ROUTES = frozenset(
    {
        ("GET", "/health"),
        *EXPECTED_APPROVED_SCHEMA_OPERATIONS.keys(),
        *EXPECTED_APPROVED_TRANSACTION_OPERATIONS.keys(),
        *EXPECTED_APPROVED_REPORT_OPERATIONS.keys(),
        *EXPECTED_APPROVED_IMPORT_OPERATIONS.keys(),
    }
)
EXPECTED_APPROVED_MOUNTED_ROUTES = frozenset(
    {
        ("GET", "/health"),
        *EXPECTED_APPROVED_SCHEMA_OPERATIONS.keys(),
        *EXPECTED_APPROVED_SESSION_OPERATIONS.keys(),
        *EXPECTED_APPROVED_TRANSACTION_OPERATIONS.keys(),
        *EXPECTED_APPROVED_REPORT_OPERATIONS.keys(),
        *EXPECTED_APPROVED_IMPORT_OPERATIONS.keys(),
    }
)

EXCLUDED_CONCRETE_OPERATIONS = frozenset(
    {
        ("POST", "/api/v1/users"),
        ("DELETE", "/api/v1/sessions"),
        ("POST", "/api/v1/password-resets"),
        ("POST", "/api/v1/password-resets/confirmations"),
        ("GET", "/api/v1/users/me"),
        ("PATCH", "/api/v1/users/me"),
        ("GET", "/api/v1/users/me/memberships"),
        ("GET", "/api/v1/households"),
        ("POST", "/api/v1/households"),
        ("GET", "/api/v1/households/{householdId}"),
        ("PATCH", "/api/v1/households/{householdId}"),
        ("POST", "/api/v1/households/{householdId}/archive"),
        ("POST", "/api/v1/households/{householdId}/leave-requests"),
        ("GET", "/api/v1/households/{householdId}/invites"),
        ("POST", "/api/v1/households/{householdId}/invites"),
        ("GET", "/api/v1/invites/{inviteId}"),
        ("POST", "/api/v1/invites/{inviteId}/accept"),
        ("POST", "/api/v1/invites/{inviteId}/decline"),
        ("POST", "/api/v1/invites/{inviteId}/revoke"),
        ("POST", "/api/v1/invites/{inviteId}/resend"),
        ("GET", "/api/v1/households/{householdId}/memberships"),
        ("GET", "/api/v1/memberships/{membershipId}"),
        ("POST", "/api/v1/memberships/{membershipId}/revoke"),
        ("POST", "/api/v1/memberships/{membershipId}/leave"),
        ("POST", "/api/v1/transactions/{transactionId}/void"),
        ("GET", "/api/v1/exports"),
        ("POST", "/api/v1/exports"),
        ("GET", "/api/v1/exports/{exportId}"),
        ("GET", "/api/v1/exports/{exportId}/files"),
        ("POST", "/api/v1/users/me/deletion-requests"),
        ("GET", "/api/v1/users/me/deletion-requests/{deletionRequestId}"),
    }
)

EXCLUDED_ROUTE_PREFIXES = (
    "/api/v1/import-jobs",
    "/api/v1/files/imports",
    "/api/v1/bank-connections",
    "/api/v1/bank-accounts",
    "/api/v1/bank-api",
    "/api/v1/sms-imports",
    "/api/v1/push-imports",
    "/api/v1/notifications/push-tokens",
    "/api/v1/broker-connections",
    "/api/v1/external-credentials",
    "/api/v1/debug",
    "/api/v1/support",
)


def _route_operations(*, include_schema_only: bool) -> set[tuple[str, str]]:
    application = create_app()
    operations: set[tuple[str, str]] = set()

    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        if include_schema_only and not route.include_in_schema:
            continue

        for method in sorted(route.methods or ()):
            if method in IGNORED_RUNTIME_METHODS:
                continue
            operations.add((method, route.path_format))

    return operations


def _canonical_openapi_operation_ids() -> dict[tuple[str, str], str]:
    operations: dict[tuple[str, str], str] = {}
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None

    for raw_line in OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if stripped == "paths:":
            in_paths = True
            continue
        if in_paths and indent == 0 and stripped.endswith(":"):
            break
        if not in_paths or not stripped or stripped.startswith("#"):
            continue

        if indent == 2 and stripped.startswith("/") and stripped.endswith(":"):
            current_path = stripped[:-1]
            current_method = None
            continue

        if current_path and indent == 4 and stripped.endswith(":"):
            method = stripped[:-1]
            current_method = method.upper() if method in HTTP_METHODS else None
            continue

        if current_path and current_method and indent == 6 and stripped.startswith("operationId:"):
            operation_id = stripped.split(":", 1)[1].strip()
            operations[(current_method, f"/api/v1{current_path}")] = operation_id

    return operations


def test_schema_included_runtime_routes_match_frozen_accounts_categories_subset() -> None:
    assert _route_operations(include_schema_only=True) == EXPECTED_SCHEMA_INCLUDED_ROUTES


def test_mounted_runtime_routes_match_frozen_accounts_categories_sessions_subset() -> None:
    mounted_operations = {
        operation
        for operation in _route_operations(include_schema_only=False)
        if operation[1] != "/api/v1/{path}"
    }

    assert mounted_operations == EXPECTED_APPROVED_MOUNTED_ROUTES


def test_no_excluded_route_family_is_mounted() -> None:
    mounted_operations = _route_operations(include_schema_only=False)
    concrete_violations = mounted_operations & EXCLUDED_CONCRETE_OPERATIONS
    prefix_violations = {
        (method, path)
        for method, path in mounted_operations
        for prefix in EXCLUDED_ROUTE_PREFIXES
        if path == prefix or path.startswith(f"{prefix}/")
    }

    assert concrete_violations == frozenset()
    assert prefix_violations == set()


def test_runtime_openapi_operation_ids_match_approved_subset(client) -> None:
    schema = client.get("/openapi.json").json()
    runtime_operation_ids = {
        (method.upper(), path): operation["operationId"]
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
        if method in HTTP_METHODS
    }

    approved_runtime_operation_ids = {
        operation: runtime_operation_ids.get(operation)
        for operation in {
            **EXPECTED_APPROVED_SCHEMA_OPERATIONS,
            **EXPECTED_APPROVED_TRANSACTION_OPERATIONS,
            **EXPECTED_APPROVED_REPORT_OPERATIONS,
            **EXPECTED_APPROVED_IMPORT_OPERATIONS,
        }
    }

    assert approved_runtime_operation_ids == {
        **EXPECTED_APPROVED_SCHEMA_OPERATIONS,
        **EXPECTED_APPROVED_TRANSACTION_OPERATIONS,
        **EXPECTED_APPROVED_REPORT_OPERATIONS,
        **EXPECTED_APPROVED_IMPORT_OPERATIONS,
    }


def test_canonical_openapi_operation_ids_match_approved_subset() -> None:
    canonical_operation_ids = _canonical_openapi_operation_ids()
    approved_canonical_operation_ids = {
        operation: canonical_operation_ids.get(operation)
        for operation in {
            **EXPECTED_APPROVED_SCHEMA_OPERATIONS,
            **EXPECTED_APPROVED_TRANSACTION_OPERATIONS,
            **EXPECTED_APPROVED_REPORT_OPERATIONS,
            **EXPECTED_APPROVED_IMPORT_OPERATIONS,
        }
    }

    assert approved_canonical_operation_ids == {
        **EXPECTED_APPROVED_SCHEMA_OPERATIONS,
        **EXPECTED_APPROVED_TRANSACTION_OPERATIONS,
        **EXPECTED_APPROVED_REPORT_OPERATIONS,
        **EXPECTED_APPROVED_IMPORT_OPERATIONS,
    }


def test_canonical_openapi_session_operation_ids_cover_mounted_session_subset() -> None:
    canonical_operation_ids = _canonical_openapi_operation_ids()
    approved_session_operation_ids = {
        operation: canonical_operation_ids.get(operation)
        for operation in EXPECTED_APPROVED_SESSION_OPERATIONS
    }

    assert approved_session_operation_ids == EXPECTED_APPROVED_SESSION_OPERATIONS


def test_canonical_openapi_excludes_unmounted_session_operations() -> None:
    canonical_operation_ids = _canonical_openapi_operation_ids()

    assert canonical_operation_ids.keys().isdisjoint(EXPECTED_UNMOUNTED_SESSION_OPERATIONS)


def test_canonical_openapi_excludes_unmounted_transfer_and_void_operations() -> None:
    canonical_operation_ids = _canonical_openapi_operation_ids()

    assert ("POST", "/api/v1/transactions/{transactionId}/void") not in canonical_operation_ids
    assert not any(
        path == "/api/v1/transfers" or path.startswith("/api/v1/transfers/")
        for _, path in canonical_operation_ids
    )
