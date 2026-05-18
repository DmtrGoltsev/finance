from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.accounts.repository import AccountRecord, reset_accounts_for_tests, seed_accounts_for_tests
from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.authz import (
    AccountOwnershipType,
    Actor,
    Membership,
    MembershipStatus,
    ResourceStatus,
)
from app.categories.repository import CategoryRecord
from app.categories.repository import repository as category_repository
from app.categories.schemas import (
    CategoryScope,
    CategoryType,
)
from app.categories.schemas import (
    RecordStatus as CategoryRecordStatus,
)
from app.main import create_app

HH_AB = "hh_ab"
HH_C = "hh_c"
MISSING_ACCOUNT_ID = "missing_privacy_probe_account"
MISSING_CATEGORY_ID = "missing_privacy_probe_category"
BASE_TIME = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)

NO_HIDDEN_MARKERS = {
    "filteredout",
    "filtered_out",
    "filtered out",
    "hiddencount",
    "hidden_count",
    "hidden count",
    "hiddenfacet",
    "hidden_facet",
    "hidden facet",
    "hiddenplaceholder",
    "hidden_placeholder",
    "hidden placeholder",
}

RESOURCE_ROUTES = {
    "accounts": {
        "list": ("GET", "/api/v1/accounts"),
        "detail": ("GET", "/api/v1/accounts/{accountId}"),
        "autocomplete": ("GET", "/api/v1/accounts/autocomplete"),
        "patch": ("PATCH", "/api/v1/accounts/{accountId}"),
    },
    "categories": {
        "list": ("GET", "/api/v1/categories"),
        "detail": ("GET", "/api/v1/categories/{categoryId}"),
        "autocomplete": ("GET", "/api/v1/categories/autocomplete"),
        "patch": ("PATCH", "/api/v1/categories/{categoryId}"),
    },
}


@dataclass(frozen=True)
class ActorCase:
    label: str
    actor: Actor
    allowed_personal_owner_id: str | None
    allowed_households: tuple[str, ...]
    forbidden_owner_ids: tuple[str, ...]
    forbidden_households: tuple[str, ...]


ACTOR_CASES = (
    ActorCase(
        label="owner_a",
        actor=Actor(
            user_id="owner_a",
            memberships=(
                Membership("owner_a", HH_AB, MembershipStatus.ACTIVE),
            ),
        ),
        allowed_personal_owner_id="owner_a",
        allowed_households=(HH_AB,),
        forbidden_owner_ids=("member_b",),
        forbidden_households=(HH_C,),
    ),
    ActorCase(
        label="member_b",
        actor=Actor(
            user_id="member_b",
            memberships=(
                Membership("member_b", HH_AB, MembershipStatus.ACTIVE),
            ),
        ),
        allowed_personal_owner_id="member_b",
        allowed_households=(HH_AB,),
        forbidden_owner_ids=("owner_a",),
        forbidden_households=(HH_C,),
    ),
    ActorCase(
        label="other_c",
        actor=Actor(
            user_id="other_c",
            memberships=(
                Membership("other_c", HH_C, MembershipStatus.ACTIVE),
            ),
        ),
        allowed_personal_owner_id=None,
        allowed_households=(HH_C,),
        forbidden_owner_ids=("owner_a", "member_b"),
        forbidden_households=(HH_AB,),
    ),
    ActorCase(
        label="invited_ab",
        actor=Actor(
            user_id="invited_ab",
            memberships=(
                Membership("invited_ab", HH_AB, MembershipStatus.INVITED),
            ),
        ),
        allowed_personal_owner_id=None,
        allowed_households=(),
        forbidden_owner_ids=("owner_a", "member_b"),
        forbidden_households=(HH_AB, HH_C),
    ),
    ActorCase(
        label="former_ab",
        actor=Actor(
            user_id="former_ab",
            memberships=(
                Membership("former_ab", HH_AB, MembershipStatus.LEFT),
            ),
        ),
        allowed_personal_owner_id=None,
        allowed_households=(),
        forbidden_owner_ids=("owner_a", "member_b"),
        forbidden_households=(HH_AB, HH_C),
    ),
)


def _account_record(
    *,
    account_id: str,
    name: str,
    ownership_type: AccountOwnershipType,
    owner_user_id: str | None = None,
    household_id: str | None = None,
    offset: int = 0,
) -> AccountRecord:
    now = BASE_TIME + timedelta(minutes=offset)
    return AccountRecord(
        id=account_id,
        name=name,
        account_type="cash",
        ownership_type=ownership_type,
        owner_user_id=owner_user_id,
        household_id=household_id,
        currency="RUB",
        initial_balance=Decimal("100.00"),
        current_balance=Decimal("100.00"),
        created_by_user_id=owner_user_id or "shared_creator",
        created_at=now,
        updated_at=now,
        version=1,
        status=ResourceStatus.ACTIVE,
    )


def _category_record(
    *,
    category_id: str,
    name: str,
    scope: CategoryScope,
    owner_user_id: str | None = None,
    household_id: str | None = None,
    offset: int = 0,
) -> CategoryRecord:
    now = BASE_TIME + timedelta(minutes=offset)
    return CategoryRecord(
        id=category_id,
        name=name,
        type=CategoryType.EXPENSE,
        scope=scope,
        owner_user_id=owner_user_id,
        household_id=household_id,
        icon_key="tag",
        color="#336699",
        status=CategoryRecordStatus.ACTIVE,
        created_by_user_id=owner_user_id or "shared_creator",
        created_at=now,
        updated_at=now,
        archived_at=None,
        deleted_at=None,
        version=1,
    )


@pytest.fixture(autouse=True)
def seeded_accounts_categories_privacy_graph() -> Iterable[None]:
    reset_accounts_for_tests()
    category_repository.reset()
    seed_accounts_for_tests(
        [
            _account_record(
                account_id="privacy_acct_owner_a_personal",
                name="Owner A Personal",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id="owner_a",
                offset=1,
            ),
            _account_record(
                account_id="privacy_acct_member_b_personal",
                name="Member B Personal",
                ownership_type=AccountOwnershipType.PERSONAL,
                owner_user_id="member_b",
                offset=2,
            ),
            _account_record(
                account_id="privacy_acct_hh_ab_shared",
                name="AB Shared",
                ownership_type=AccountOwnershipType.SHARED,
                household_id=HH_AB,
                offset=3,
            ),
            _account_record(
                account_id="privacy_acct_hh_c_shared",
                name="C Shared",
                ownership_type=AccountOwnershipType.SHARED,
                household_id=HH_C,
                offset=4,
            ),
        ]
    )
    category_repository.reset(
        (
            _category_record(
                category_id="privacy_cat_owner_a_personal",
                name="Owner A Personal",
                scope=CategoryScope.PERSONAL,
                owner_user_id="owner_a",
                offset=1,
            ),
            _category_record(
                category_id="privacy_cat_member_b_personal",
                name="Member B Personal",
                scope=CategoryScope.PERSONAL,
                owner_user_id="member_b",
                offset=2,
            ),
            _category_record(
                category_id="privacy_cat_hh_ab",
                name="AB Household",
                scope=CategoryScope.HOUSEHOLD,
                household_id=HH_AB,
                offset=3,
            ),
            _category_record(
                category_id="privacy_cat_hh_c",
                name="C Household",
                scope=CategoryScope.HOUSEHOLD,
                household_id=HH_C,
                offset=4,
            ),
        )
    )
    yield
    reset_accounts_for_tests()
    category_repository.reset()


def _route_signature(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{param}", path)


def _route_exists(app: FastAPI, *, method: str, path: str) -> bool:
    expected_path = _route_signature(path)
    for route in app.routes:
        route_methods = getattr(route, "methods", set()) or set()
        route_path = _route_signature(getattr(route, "path", ""))
        if method in route_methods and route_path == expected_path:
            return True
    return False


def _skip_if_routes_missing(app: FastAPI, resource: str, route_names: Iterable[str]) -> None:
    missing = [
        f"{method} {path}"
        for name in route_names
        for method, path in (RESOURCE_ROUTES[resource][name],)
        if not _route_exists(app, method=method, path=path)
    ]
    if missing:
        dependency = (
            "W2-S4 accounts routes"
            if resource == "accounts"
            else "W2-S5 categories routes"
        )
        pytest.skip(f"pending {dependency}: missing {', '.join(missing)}")


def _client_for_actor(app: FastAPI, actor: Actor) -> TestClient:
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    return TestClient(app)


def _json(response: Any) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(f"response body is not JSON: {response.text!r}") from exc


def _all_dicts(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(_all_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_all_dicts(child))
    return found


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_all_strings(child))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for child in value:
            strings.extend(_all_strings(child))
        return strings
    return []


def _resource_items(body: Any) -> list[Mapping[str, Any]]:
    return [item for item in _all_dicts(body) if isinstance(item.get("id"), str)]


def _ids(body: Any) -> set[str]:
    return {str(item["id"]) for item in _resource_items(body)}


def _assert_no_hidden_markers(body: Any) -> None:
    lower_values = [value.lower() for value in _all_strings(body)]
    leaked = [
        marker
        for marker in NO_HIDDEN_MARKERS
        if any(marker in value for value in lower_values)
    ]
    assert leaked == []


def _assert_account_visibility(body: Any, case: ActorCase) -> None:
    items = _resource_items(body)
    for item in items:
        assert item.get("ownerUserId") not in case.forbidden_owner_ids
        assert item.get("householdId") not in case.forbidden_households

    if case.allowed_personal_owner_id is not None:
        assert any(item.get("ownerUserId") == case.allowed_personal_owner_id for item in items)

    for household_id in case.allowed_households:
        assert any(item.get("householdId") == household_id for item in items)


def _assert_category_visibility(body: Any, case: ActorCase) -> None:
    items = _resource_items(body)
    for item in items:
        assert item.get("ownerUserId") not in case.forbidden_owner_ids
        assert item.get("householdId") not in case.forbidden_households

    if case.allowed_personal_owner_id is not None:
        assert any(item.get("ownerUserId") == case.allowed_personal_owner_id for item in items)

    for household_id in case.allowed_households:
        assert any(item.get("householdId") == household_id for item in items)


def _assert_no_forbidden_scope(body: Any, case: ActorCase) -> None:
    for item in _resource_items(body):
        assert item.get("ownerUserId") not in case.forbidden_owner_ids
        assert item.get("householdId") not in case.forbidden_households


def _find_item(
    body: Any,
    *,
    owner_user_id: str | None = None,
    household_id: str | None = None,
) -> Mapping[str, Any]:
    for item in _resource_items(body):
        if owner_user_id is not None and item.get("ownerUserId") == owner_user_id:
            return item
        if household_id is not None and item.get("householdId") == household_id:
            return item
    raise AssertionError(
        f"fixture item missing from visible response: owner={owner_user_id!r}, "
        f"household={household_id!r}"
    )


def _normalize_public_shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if str(key).lower() in {"requestid", "request_id", "traceid", "trace_id"}:
                normalized[str(key)] = "<request-id>"
            else:
                normalized[str(key)] = _normalize_public_shape(child)
        return normalized
    if isinstance(value, list):
        return [_normalize_public_shape(item) for item in value]
    return value


def _assert_same_public_denial_shape(first: Any, second: Any) -> None:
    assert first.status_code == second.status_code
    assert first.status_code in {403, 404}
    assert _normalize_public_shape(_json(first)) == _normalize_public_shape(_json(second))
    _assert_no_hidden_markers(_json(first))
    _assert_no_hidden_markers(_json(second))


def _get_list(app: FastAPI, case: ActorCase, resource: str) -> Any:
    with _client_for_actor(app, case.actor) as client:
        response = client.get(f"/api/v1/{resource}")

    assert response.status_code == 200
    body = _json(response)
    _assert_no_hidden_markers(body)
    return body


def _get_autocomplete(app: FastAPI, case: ActorCase, resource: str) -> Any:
    with _client_for_actor(app, case.actor) as client:
        response = client.get(f"/api/v1/{resource}/autocomplete")

    assert response.status_code == 200
    body = _json(response)
    _assert_no_hidden_markers(body)
    return body


def test_accounts_privacy_matrix_for_list_detail_autocomplete() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "accounts", ("list", "detail", "autocomplete"))

    visible_lists = {case.label: _get_list(app, case, "accounts") for case in ACTOR_CASES}

    for case in ACTOR_CASES:
        _assert_account_visibility(visible_lists[case.label], case)
        autocomplete = _get_autocomplete(app, case, "accounts")
        assert _ids(autocomplete).issubset(_ids(visible_lists[case.label]))

    owner_personal = _find_item(visible_lists["owner_a"], owner_user_id="owner_a")
    shared_ab = _find_item(visible_lists["owner_a"], household_id=HH_AB)

    with _client_for_actor(app, ACTOR_CASES[0].actor) as client:
        owner_detail = client.get(f"/api/v1/accounts/{owner_personal['id']}")
        shared_detail_for_owner = client.get(f"/api/v1/accounts/{shared_ab['id']}")

    assert owner_detail.status_code == 200
    assert shared_detail_for_owner.status_code == 200
    _assert_no_forbidden_scope(_json(owner_detail), ACTOR_CASES[0])
    _assert_no_forbidden_scope(_json(shared_detail_for_owner), ACTOR_CASES[0])
    assert _find_item(_json(owner_detail), owner_user_id="owner_a")["id"] == owner_personal["id"]
    assert _find_item(_json(shared_detail_for_owner), household_id=HH_AB)["id"] == shared_ab["id"]

    with _client_for_actor(app, ACTOR_CASES[1].actor) as client:
        shared_detail_for_member = client.get(f"/api/v1/accounts/{shared_ab['id']}")

    assert shared_detail_for_member.status_code == 200
    _assert_no_forbidden_scope(_json(shared_detail_for_member), ACTOR_CASES[1])
    assert _find_item(_json(shared_detail_for_member), household_id=HH_AB)["id"] == shared_ab["id"]

    for case in ACTOR_CASES[2:]:
        with _client_for_actor(app, case.actor) as client:
            response = client.get(f"/api/v1/accounts/{shared_ab['id']}")
        assert response.status_code in {403, 404}
        _assert_no_hidden_markers(_json(response))


def test_categories_privacy_matrix_for_list_detail_autocomplete() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "categories", ("list", "detail", "autocomplete"))

    visible_lists = {case.label: _get_list(app, case, "categories") for case in ACTOR_CASES}

    for case in ACTOR_CASES:
        _assert_category_visibility(visible_lists[case.label], case)
        autocomplete = _get_autocomplete(app, case, "categories")
        assert _ids(autocomplete).issubset(_ids(visible_lists[case.label]))

    owner_personal = _find_item(visible_lists["owner_a"], owner_user_id="owner_a")
    household_ab = _find_item(visible_lists["owner_a"], household_id=HH_AB)

    with _client_for_actor(app, ACTOR_CASES[0].actor) as client:
        owner_detail = client.get(f"/api/v1/categories/{owner_personal['id']}")
        household_detail_for_owner = client.get(f"/api/v1/categories/{household_ab['id']}")

    assert owner_detail.status_code == 200
    assert household_detail_for_owner.status_code == 200
    _assert_no_forbidden_scope(_json(owner_detail), ACTOR_CASES[0])
    _assert_no_forbidden_scope(_json(household_detail_for_owner), ACTOR_CASES[0])
    assert _find_item(_json(owner_detail), owner_user_id="owner_a")["id"] == owner_personal["id"]
    owner_household_detail = _find_item(
        _json(household_detail_for_owner),
        household_id=HH_AB,
    )
    assert owner_household_detail["id"] == household_ab["id"]

    with _client_for_actor(app, ACTOR_CASES[1].actor) as client:
        household_detail_for_member = client.get(f"/api/v1/categories/{household_ab['id']}")

    assert household_detail_for_member.status_code == 200
    _assert_no_forbidden_scope(_json(household_detail_for_member), ACTOR_CASES[1])
    member_household_detail = _find_item(
        _json(household_detail_for_member),
        household_id=HH_AB,
    )
    assert member_household_detail["id"] == household_ab["id"]

    for case in ACTOR_CASES[2:]:
        with _client_for_actor(app, case.actor) as client:
            response = client.get(f"/api/v1/categories/{household_ab['id']}")
        assert response.status_code in {403, 404}
        _assert_no_hidden_markers(_json(response))


def test_accounts_missing_vs_inaccessible_direct_ids_have_same_public_shape() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "accounts", ("list", "detail"))

    owner_list = _get_list(app, ACTOR_CASES[0], "accounts")
    owner_personal = _find_item(owner_list, owner_user_id="owner_a")

    with _client_for_actor(app, ACTOR_CASES[1].actor) as client:
        inaccessible = client.get(f"/api/v1/accounts/{owner_personal['id']}")
        missing = client.get(f"/api/v1/accounts/{MISSING_ACCOUNT_ID}")

    _assert_same_public_denial_shape(inaccessible, missing)
    assert str(owner_personal["id"]) not in inaccessible.text


def test_categories_missing_vs_inaccessible_direct_ids_have_same_public_shape() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "categories", ("list", "detail"))

    owner_list = _get_list(app, ACTOR_CASES[0], "categories")
    owner_personal = _find_item(owner_list, owner_user_id="owner_a")

    with _client_for_actor(app, ACTOR_CASES[1].actor) as client:
        inaccessible = client.get(f"/api/v1/categories/{owner_personal['id']}")
        missing = client.get(f"/api/v1/categories/{MISSING_CATEGORY_ID}")

    _assert_same_public_denial_shape(inaccessible, missing)
    assert str(owner_personal["id"]) not in inaccessible.text


def test_accounts_reject_immutable_ownership_updates_safely() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "accounts", ("list", "detail", "patch"))

    owner_list = _get_list(app, ACTOR_CASES[0], "accounts")
    owner_personal = _find_item(owner_list, owner_user_id="owner_a")

    with _client_for_actor(app, ACTOR_CASES[0].actor) as client:
        response = client.patch(
            f"/api/v1/accounts/{owner_personal['id']}",
            json={
                "ownershipType": "shared",
                "ownerUserId": "member_b",
                "householdId": HH_AB,
                "version": owner_personal.get("version", 1),
            },
        )
        after = client.get(f"/api/v1/accounts/{owner_personal['id']}")

    assert response.status_code in {400, 403, 409, 422}
    _assert_no_hidden_markers(_json(response))
    assert after.status_code == 200
    after_body = _json(after)
    after_item = _find_item(after_body, owner_user_id="owner_a")
    assert after_item.get("ownershipType") == "personal"
    assert after_item.get("householdId") in {None, ""}


def test_categories_reject_immutable_scope_updates_safely() -> None:
    app = create_app()
    _skip_if_routes_missing(app, "categories", ("list", "detail", "patch"))

    owner_list = _get_list(app, ACTOR_CASES[0], "categories")
    owner_personal = _find_item(owner_list, owner_user_id="owner_a")

    with _client_for_actor(app, ACTOR_CASES[0].actor) as client:
        response = client.patch(
            f"/api/v1/categories/{owner_personal['id']}",
            json={
                "scope": "household",
                "ownerUserId": "member_b",
                "householdId": HH_AB,
                "version": owner_personal.get("version", 1),
            },
        )
        after = client.get(f"/api/v1/categories/{owner_personal['id']}")

    assert response.status_code in {400, 403, 409, 422}
    _assert_no_hidden_markers(_json(response))
    assert after.status_code == 200
    after_body = _json(after)
    after_item = _find_item(after_body, owner_user_id="owner_a")
    assert after_item.get("scope") == "personal"
    assert after_item.get("householdId") in {None, ""}
