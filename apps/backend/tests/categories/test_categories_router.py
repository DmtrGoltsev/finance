from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import Actor, Membership, MembershipStatus
from app.categories.repository import CategoryRecord, repository
from app.categories.schemas import CategoryScope, CategoryType, RecordStatus
from app.main import create_app

USER_A = "usr_a"
USER_B = "usr_b"
USER_C = "usr_c"
USER_INVITED = "usr_invited"
USER_FORMER = "usr_former"
HOUSEHOLD_AB = "hh_ab"
HOUSEHOLD_C = "hh_c"
BASE_TIME = datetime(2026, 5, 17, 10, 0, tzinfo=UTC)


def _record(
    *,
    id: str,
    name: str,
    type: CategoryType = CategoryType.EXPENSE,
    scope: CategoryScope = CategoryScope.PERSONAL,
    owner_user_id: str | None = USER_A,
    household_id: str | None = None,
    status: RecordStatus = RecordStatus.ACTIVE,
    offset: int = 0,
) -> CategoryRecord:
    now = BASE_TIME + timedelta(minutes=offset)
    return CategoryRecord(
        id=id,
        name=name,
        type=type,
        scope=scope,
        owner_user_id=owner_user_id,
        household_id=household_id,
        icon_key="tag",
        color="#336699",
        status=status,
        created_by_user_id=owner_user_id or USER_A,
        created_at=now,
        updated_at=now,
        archived_at=now if status == RecordStatus.ARCHIVED else None,
        deleted_at=now if status == RecordStatus.DELETED else None,
        version=1,
    )


def _seed_categories() -> None:
    repository.reset(
        (
            _record(id="cat_a_food", name="A Food", offset=1),
            _record(id="cat_b_private", name="B Private Hidden", owner_user_id=USER_B, offset=2),
            _record(
                id="cat_ab_family",
                name="Family Groceries",
                scope=CategoryScope.HOUSEHOLD,
                owner_user_id=None,
                household_id=HOUSEHOLD_AB,
                offset=3,
            ),
            _record(
                id="cat_c_family",
                name="C Household",
                scope=CategoryScope.HOUSEHOLD,
                owner_user_id=None,
                household_id=HOUSEHOLD_C,
                offset=4,
            ),
            _record(
                id="cat_a_archived",
                name="Old Salary",
                type=CategoryType.INCOME,
                status=RecordStatus.ARCHIVED,
                offset=5,
            ),
            _record(
                id="cat_a_deleted",
                name="Deleted Personal",
                status=RecordStatus.DELETED,
                offset=6,
            ),
        )
    )


@pytest.fixture(autouse=True)
def seeded_repository() -> Iterator[None]:
    _seed_categories()
    yield
    repository.reset()


def _actor(user_id: str, *memberships: Membership) -> Actor:
    return Actor(user_id=user_id, memberships=memberships, request_id="req-categories-test")


def _membership(user_id: str, household_id: str, status: MembershipStatus) -> Membership:
    return Membership(user_id=user_id, household_id=household_id, status=status)


ACTOR_A = _actor(
    USER_A,
    _membership(USER_A, HOUSEHOLD_AB, MembershipStatus.ACTIVE),
)
ACTOR_B = _actor(
    USER_B,
    _membership(USER_B, HOUSEHOLD_AB, MembershipStatus.ACTIVE),
)
ACTOR_C = _actor(
    USER_C,
    _membership(USER_C, HOUSEHOLD_C, MembershipStatus.ACTIVE),
)
ACTOR_INVITED = _actor(
    USER_INVITED,
    _membership(USER_INVITED, HOUSEHOLD_AB, MembershipStatus.INVITED),
)
ACTOR_FORMER = _actor(
    USER_FORMER,
    _membership(USER_FORMER, HOUSEHOLD_AB, MembershipStatus.LEFT),
)


@contextmanager
def _client_for(actor: Actor) -> Iterator[TestClient]:
    app: FastAPI = create_app()
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    with TestClient(app) as client:
        yield client


def _assert_error_code(response_body: dict[str, Any], expected_code: str) -> dict[str, Any]:
    assert set(response_body) == {"error"}
    error = response_body["error"]
    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert isinstance(error["requestId"], str)
    return error


def test_list_only_returns_categories_visible_to_actor_without_hidden_counts() -> None:
    with _client_for(ACTOR_A) as client:
        response = client.get("/api/v1/categories", params={"sort": "name"})

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}

    assert ids == {"cat_a_food", "cat_ab_family", "cat_a_archived"}
    assert "cat_b_private" not in ids
    assert "cat_c_family" not in ids
    assert "cat_a_deleted" not in ids
    assert set(body["page"]) == {"limit", "nextCursor", "hasMore"}
    serialized = response.text
    assert "totalCount" not in serialized
    assert "usageCount" not in serialized
    assert "transactionCount" not in serialized


def test_search_and_autocomplete_filter_after_visibility() -> None:
    with _client_for(ACTOR_A) as client:
        hidden_search = client.get("/api/v1/categories", params={"q": "Hidden"})
        autocomplete = client.get("/api/v1/categories/autocomplete", params={"q": "Family"})

    assert hidden_search.status_code == 200
    assert hidden_search.json()["items"] == []

    assert autocomplete.status_code == 200
    assert autocomplete.json()["items"] == [
        {
            "id": "cat_ab_family",
            "name": "Family Groceries",
            "type": "expense",
            "scope": "household",
            "householdId": HOUSEHOLD_AB,
            "iconKey": "tag",
            "color": "#336699",
        }
    ]


def test_household_visibility_requires_active_membership_for_b_c_invited_and_former() -> None:
    cases = [
        (ACTOR_B, {"cat_ab_family"}),
        (ACTOR_C, {"cat_c_family"}),
        (ACTOR_INVITED, set()),
        (ACTOR_FORMER, set()),
    ]

    for actor, expected_ids in cases:
        with _client_for(actor) as client:
            response = client.get("/api/v1/categories", params={"scope": "household"})

        assert response.status_code == 200
        assert {item["id"] for item in response.json()["items"]} == expected_ids


def test_get_uses_same_neutral_shape_for_missing_and_inaccessible_category_ids() -> None:
    with _client_for(ACTOR_A) as client:
        missing = client.get("/api/v1/categories/cat_does_not_exist")
        inaccessible = client.get("/api/v1/categories/cat_b_private")

    assert missing.status_code == 404
    assert inaccessible.status_code == 404
    assert missing.json() == inaccessible.json()
    _assert_error_code(missing.json(), "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE")
    assert "B Private Hidden" not in missing.text + inaccessible.text
    assert "cat_b_private" not in missing.text + inaccessible.text


def test_create_personal_and_household_categories_enforce_scope_boundary() -> None:
    with _client_for(ACTOR_A) as client:
        personal = client.post(
            "/api/v1/categories",
            json={
                "name": "Coffee",
                "type": "expense",
                "scope": "personal",
                "iconKey": "cup",
                "color": "#112233",
            },
        )
        household = client.post(
            "/api/v1/categories",
            json={
                "name": "Shared Bonus",
                "type": "income",
                "scope": "household",
                "householdId": HOUSEHOLD_AB,
            },
        )

    assert personal.status_code == 201
    personal_data = personal.json()["data"]
    assert personal_data["ownerUserId"] == USER_A
    assert personal_data["householdId"] is None
    assert personal_data["scope"] == "personal"

    assert household.status_code == 201
    household_data = household.json()["data"]
    assert household_data["ownerUserId"] is None
    assert household_data["householdId"] == HOUSEHOLD_AB
    assert household_data["scope"] == "household"

    with _client_for(ACTOR_INVITED) as client:
        denied = client.post(
            "/api/v1/categories",
            json={
                "name": "Not Allowed",
                "type": "expense",
                "scope": "household",
                "householdId": HOUSEHOLD_AB,
            },
        )

    assert denied.status_code == 404
    _assert_error_code(denied.json(), "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE")


def test_update_keeps_scope_owner_and_household_immutable() -> None:
    with _client_for(ACTOR_A) as client:
        blocked = client.patch(
            "/api/v1/categories/cat_a_food",
            json={
                "name": "Moved",
                "scope": "household",
                "householdId": HOUSEHOLD_AB,
                "ownerUserId": USER_B,
            },
        )
        after = client.get("/api/v1/categories/cat_a_food")

    assert blocked.status_code == 422
    assert after.status_code == 200
    data = after.json()["data"]
    assert data["name"] == "A Food"
    assert data["scope"] == "personal"
    assert data["ownerUserId"] == USER_A
    assert data["householdId"] is None


def test_update_archive_restore_and_delete_lifecycle() -> None:
    with _client_for(ACTOR_A) as client:
        updated = client.patch(
            "/api/v1/categories/cat_a_food",
            json={"name": "Food Updated", "iconKey": "fork", "color": "#445566", "version": 1},
        )
        archived = client.post("/api/v1/categories/cat_a_food/archive")
        update_archived = client.patch("/api/v1/categories/cat_a_food", json={"name": "Nope"})
        restored = client.post("/api/v1/categories/cat_a_food/restore")
        deleted = client.delete("/api/v1/categories/cat_a_food")
        get_deleted = client.get("/api/v1/categories/cat_a_food")
        list_after_delete = client.get("/api/v1/categories")

    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "Food Updated"
    assert updated.json()["data"]["scope"] == "personal"

    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    assert update_archived.status_code == 409
    _assert_error_code(update_archived.json(), "ARCHIVED_RECORD_NOT_MUTABLE")

    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "active"
    assert deleted.status_code == 204
    assert get_deleted.status_code == 404
    assert "cat_a_food" not in {item["id"] for item in list_after_delete.json()["items"]}


def test_default_current_actor_boundary_denies_categories_without_override() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/categories")

    assert response.status_code == 401
    _assert_error_code(response.json(), "AUTHENTICATION_REQUIRED")
