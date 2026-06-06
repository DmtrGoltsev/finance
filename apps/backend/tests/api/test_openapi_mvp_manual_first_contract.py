from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
OPENAPI_CONTRACT_PATH = REPO_ROOT / "api" / "openapi" / "openapi.yaml"


def _contract_text() -> str:
    return OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8")


def _schema_block(schema_name: str) -> list[str]:
    marker = f"    {schema_name}:"
    lines = _contract_text().splitlines()
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


def _contract_paths() -> set[str]:
    paths: set[str] = set()
    in_paths = False

    for raw_line in _contract_text().splitlines():
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if stripped == "paths:":
            in_paths = True
            continue

        if in_paths and indent == 0 and stripped.endswith(":"):
            break

        if in_paths and indent == 2 and stripped.startswith("/") and stripped.endswith(":"):
            paths.add(stripped[:-1])

    return paths


def _contract_methods(path_name: str) -> set[str]:
    methods: set[str] = set()
    in_paths = False
    in_path = False

    for raw_line in _contract_text().splitlines():
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if stripped == "paths:":
            in_paths = True
            continue

        if in_paths and indent == 0 and stripped.endswith(":"):
            break

        if not in_paths:
            continue

        if indent == 2 and stripped.startswith("/") and stripped.endswith(":"):
            in_path = stripped[:-1] == path_name
            continue

        if in_path and indent == 4 and stripped.endswith(":"):
            method = stripped[:-1]
            if method in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
                methods.add(method.upper())

    return methods


def test_openapi_contains_manual_first_mvp_route_families() -> None:
    paths = _contract_paths()

    required_paths = {
        "/users",
        "/sessions",
        "/sessions/current",
        "/accounts",
        "/accounts/{accountId}",
        "/accounts/{accountId}/archive",
        "/accounts/{accountId}/restore",
        "/accounts/autocomplete",
        "/categories",
        "/categories/{categoryId}",
        "/categories/{categoryId}/archive",
        "/categories/{categoryId}/restore",
        "/categories/autocomplete",
        "/transactions",
        "/transactions/{transactionId}",
        "/transactions/{transactionId}/restore",
        "/transactions/autocomplete",
        "/capture-drafts",
        "/capture-drafts/screenshot-ocr",
        "/capture-drafts/category-mappings",
        "/capture-drafts/{draftId}",
        "/capture-drafts/{draftId}/confirm",
        "/capture-drafts/{draftId}/discard",
        "/reports/summary",
        "/reports/category-breakdown",
        "/reports/account-balances",
        "/reports/cash-flow",
        "/reports/transactions",
        "/planning/plans",
        "/planning/plans/history",
        "/planning/plans/{planId}",
        "/planning/plans/{planId}/income-sources",
        "/planning/plans/{planId}/allocations",
        "/planning/plans/{planId}/copy",
        "/planning/income-sources/{incomeSourceId}",
        "/planning/income-sources/{incomeSourceId}/confirm",
        "/planning/allocations/{allocationId}",
    }

    assert paths == required_paths


def test_openapi_sessions_surface_matches_mounted_mvp_subset() -> None:
    assert _contract_methods("/users") == {"POST"}
    assert _contract_methods("/sessions") == {"POST"}
    assert _contract_methods("/sessions/current") == {"GET", "DELETE"}


def test_openapi_excludes_post_mvp_import_bank_sms_push_broker_routes() -> None:
    paths = _contract_paths()
    excluded_prefixes = (
        "/users/me",
        "/password-resets",
        "/households",
        "/invites",
        "/memberships",
        "/imports",
        "/import-jobs",
        "/files/imports",
        "/bank-connections",
        "/bank-accounts",
        "/bank-api",
        "/sms-imports",
        "/push-imports",
        "/notifications/push-tokens",
        "/broker-connections",
        "/external-credentials",
        "/exports",
        "/transfers",
    )

    violations = {
        path
        for path in paths
        for prefix in excluded_prefixes
        if path == prefix or path.startswith(f"{prefix}/")
    }

    assert violations == set()
    assert "/transactions/{transactionId}/void" not in paths


def test_openapi_capture_screenshot_ocr_contract_is_structured_only() -> None:
    contract = _contract_text()

    assert "/capture-drafts/screenshot-ocr:" in contract
    assert "multipart/form-data:" in contract
    assert "$ref: '#/components/schemas/ScreenshotOcrEnvelope'" in contract
    assert "/capture-drafts/category-mappings:" in contract
    assert "$ref: '#/components/schemas/CaptureCategoryMappingPutRequest'" in contract

    forbidden_fields = (
        "rawImage",
        "rawScreenshot",
        "rawOcrText",
        "ocrText:",
        "body:",
        "text:",
    )
    for field_name in forbidden_fields:
        assert field_name not in contract


def test_openapi_manual_first_enum_boundaries() -> None:
    assert _inline_array_value(_schema_block("AccountType"), "enum") == [
        "cash",
        "bank",
        "card",
        "deposit",
        "brokerage",
        "metal",
        "other",
    ]
    assert _inline_array_value(_schema_block("TransactionType"), "enum") == [
        "income",
        "expense",
        "transfer",
        "brokerage",
        "asset_buy",
        "asset_sell",
        "interest",
        "dividend",
        "adjustment",
    ]
    assert _inline_array_value(_schema_block("SourceType"), "enum") == ["manual"]
    assert _inline_array_value(_schema_block("CaptureSource"), "enum") == [
        "screenshot",
    ]
    contract = _contract_text()
    forbidden_capture_fields = (
        "raw" + "Notification",
        "message" + "Text",
        "notification" + "Text",
    )
    for field_name in forbidden_capture_fields:
        assert field_name not in contract
    assert _inline_array_value(_schema_block("ReportMode"), "enum") == [
        "shared_family_report",
        "combined_viewer_overview",
    ]
    assert _inline_array_value(_schema_block("TransferScope"), "enum") == [
        "personal_same_owner",
        "household_same_household",
    ]

    reserved_source_values = set(
        _inline_array_value(_schema_block("SourceType"), "x-reserved-post-mvp-values")
    )
    assert {"file_import", "bank_api", "sms", "push"} <= reserved_source_values


def test_openapi_canonical_error_envelope_shape() -> None:
    error_envelope = "\n".join(_schema_block("ErrorEnvelope"))
    error_dto = "\n".join(_schema_block("ErrorDto"))
    error_detail = "\n".join(_schema_block("ErrorDetail"))

    assert "required: [error]" in error_envelope
    assert "$ref: '#/components/schemas/ErrorDto'" in error_envelope
    assert "required: [code, message, requestId]" in error_dto
    assert "Field-level details for caller-supplied invalid fields only" in error_detail
    assert "hidden object names" in error_detail
    assert "raw payloads" in error_detail


def test_openapi_confidence_regex_is_fully_grouped() -> None:
    contract = _contract_text()

    assert "pattern: '^0(\\.[0-9]+)?|1(\\.0+)?$'" not in contract
    assert contract.count("pattern: '^(0(\\.[0-9]+)?|1(\\.0+)?)$'") >= 3
