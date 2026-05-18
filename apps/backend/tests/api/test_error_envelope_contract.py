from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.accounts.repository import AccountRecord, reset_accounts_for_tests, seed_accounts_for_tests
from app.accounts.router import account_service_for_request
from app.accounts.service import AccountServiceError
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import (
    AccountOwnershipType,
    Actor,
    DenialReason,
    Membership,
    MembershipStatus,
    ResourceStatus,
)
from app.categories.repository import CategoryRecord
from app.categories.repository import repository as category_repository
from app.categories.router import category_service_for_request
from app.categories.schemas import CategoryScope, CategoryType
from app.categories.schemas import RecordStatus as CategoryRecordStatus
from app.main import create_app

BASE_TIME = datetime(2026, 5, 17, 16, 0, tzinfo=UTC)
REQUEST_ID = "req-error-contract"


def _actor(user_id: str) -> Actor:
    return Actor(
        user_id=user_id,
        request_id=REQUEST_ID,
        memberships=(Membership(user_id, "hh_visible", MembershipStatus.ACTIVE),),
    )


@pytest.fixture(autouse=True)
def reset_runtime_repositories() -> Iterator[None]:
    reset_accounts_for_tests()
    category_repository.reset()
    yield
    reset_accounts_for_tests()
    category_repository.reset()


def _app_for_actor(actor: Actor | None = None) -> FastAPI:
    app = create_app()
    if actor is not None:
        app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    return app


def _assert_error_envelope(
    body: dict[str, Any],
    *,
    code: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    assert set(body) == {"error"}
    error = body["error"]
    assert isinstance(error["code"], str)
    assert isinstance(error["message"], str)
    assert isinstance(error["requestId"], str)
    if code is not None:
        assert error["code"] == code
    if request_id is not None:
        assert error["requestId"] == request_id
    return error


def test_health_remains_unaffected_by_api_error_envelope() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mounted_auth_required_error_uses_canonical_envelope() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/accounts",
            headers={
                "Authorization": "Bearer raw-token-must-not-echo",
                "X-Request-ID": REQUEST_ID,
            },
        )

    assert response.status_code == 401
    _assert_error_envelope(
        response.json(),
        code="AUTHENTICATION_REQUIRED",
        request_id=REQUEST_ID,
    )
    public_body = response.text.lower()
    assert "raw-token-must-not-echo" not in public_body
    assert "bearer" not in public_body


def test_api_not_found_uses_canonical_envelope() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/password-resets",
            json={"email": "owner@example.test", "password": "secret-must-not-echo"},
            headers={"X-Request-ID": REQUEST_ID},
        )

    assert response.status_code == 404
    _assert_error_envelope(
        response.json(),
        code="RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
        request_id=REQUEST_ID,
    )
    assert "secret-must-not-echo" not in response.text


def test_forbidden_route_error_uses_canonical_envelope() -> None:
    class ForbiddenAccountService:
        def list_accounts(self, **_: object) -> object:
            raise AccountServiceError(DenialReason.ACTION_NOT_ALLOWED)

    app = _app_for_actor(_actor("owner_a"))
    app.dependency_overrides[account_service_for_request] = ForbiddenAccountService

    with TestClient(app) as client:
        response = client.get("/api/v1/accounts", headers={"X-Request-ID": REQUEST_ID})

    assert response.status_code == 403
    _assert_error_envelope(response.json(), code="ACTION_NOT_ALLOWED", request_id=REQUEST_ID)


def test_validation_error_uses_sanitized_canonical_envelope() -> None:
    app = _app_for_actor(_actor("owner_a"))
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/accounts",
            params={"limit": 0},
            headers={"X-Request-ID": REQUEST_ID},
        )

    assert response.status_code == 422
    error = _assert_error_envelope(
        response.json(),
        code="VALIDATION_FAILED",
        request_id=REQUEST_ID,
    )
    assert error["details"]
    assert "input" not in response.text.lower()


def test_accounts_missing_and_inaccessible_ids_keep_neutral_error_envelope() -> None:
    seed_accounts_for_tests(
        [
            AccountRecord(
                id="hidden_account_id_must_not_echo",
                name="Hidden Personal",
                account_type="cash",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id="owner_a",
                household_id=None,
                currency="RUB",
                initial_balance=Decimal("10.00"),
                current_balance=Decimal("10.00"),
                created_by_user_id="owner_a",
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
                status=ResourceStatus.ACTIVE,
            )
        ]
    )
    app = _app_for_actor(_actor("member_b"))

    with TestClient(app) as client:
        inaccessible = client.get("/api/v1/accounts/hidden_account_id_must_not_echo")
        missing = client.get("/api/v1/accounts/missing_account_id")

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json()
    _assert_error_envelope(
        inaccessible.json(),
        code="RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
        request_id=REQUEST_ID,
    )
    assert "hidden_account_id_must_not_echo" not in inaccessible.text


def test_categories_missing_and_inaccessible_ids_keep_neutral_error_envelope() -> None:
    category_repository.reset(
        (
            CategoryRecord(
                id="hidden_category_id_must_not_echo",
                name="Hidden Category",
                type=CategoryType.EXPENSE,
                scope=CategoryScope.PERSONAL,
                owner_user_id="owner_a",
                household_id=None,
                icon_key="tag",
                color="#336699",
                status=CategoryRecordStatus.ACTIVE,
                created_by_user_id="owner_a",
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                archived_at=None,
                deleted_at=None,
                version=1,
            ),
        )
    )
    app = _app_for_actor(_actor("member_b"))

    with TestClient(app) as client:
        inaccessible = client.get("/api/v1/categories/hidden_category_id_must_not_echo")
        missing = client.get("/api/v1/categories/missing_category_id")

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json()
    _assert_error_envelope(
        inaccessible.json(),
        code="RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE",
        request_id=REQUEST_ID,
    )
    assert "hidden_category_id_must_not_echo" not in inaccessible.text


def test_unhandled_mounted_route_error_uses_generic_500_envelope() -> None:
    class ExplodingCategoryService:
        def list(self, **_: object) -> object:
            raise RuntimeError("secret runtime detail must not echo")

    app = _app_for_actor(_actor("owner_a"))
    app.dependency_overrides[category_service_for_request] = ExplodingCategoryService

    with TestClient(app) as client:
        response = client.get("/api/v1/categories", headers={"X-Request-ID": REQUEST_ID})

    assert response.status_code == 500
    _assert_error_envelope(response.json(), code="INTERNAL_ERROR", request_id=REQUEST_ID)
    assert "secret runtime detail" not in response.text
