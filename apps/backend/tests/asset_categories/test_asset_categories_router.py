from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_context import fixed_actor_provider_for_tests, provide_actor
from app.asset_categories.repository import repository
from app.authz import Actor, Membership, MembershipStatus
from app.main import create_app

USER_A = "usr_a"
USER_INVITED = "usr_invited"
HOUSEHOLD_AB = "hh_ab"


@pytest.fixture(autouse=True)
def reset_repository() -> Iterator[None]:
    repository.reset()
    yield
    repository.reset()


def _actor(user_id: str, status: MembershipStatus = MembershipStatus.ACTIVE) -> Actor:
    return Actor(
        user_id=user_id,
        memberships=(
            Membership(user_id=user_id, household_id=HOUSEHOLD_AB, status=status),
        ),
        request_id=f"req-{user_id}",
    )


@contextmanager
def _client_for(actor: Actor) -> Iterator[TestClient]:
    app: FastAPI = create_app()
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)
    with TestClient(app) as client:
        yield client


def test_asset_category_crud_list_archive_restore_contract() -> None:
    with _client_for(_actor(USER_A)) as client:
        personal = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Brokerage",
                "scopeType": "personal",
                "currency": "RUB",
                "assetType": "brokerage",
                "manualAmount": "123.4500",
                "isInvestment": True,
            },
        )
        household = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Family Metal",
                "scopeType": "household",
                "householdId": HOUSEHOLD_AB,
                "currency": "RUB",
                "assetType": "metal",
            },
        )
        items = client.get("/api/v1/asset-categories", params={"isInvestment": True})

    assert personal.status_code == 201, personal.text
    data = personal.json()["data"]
    assert data["ownerUserId"] == USER_A
    assert data["manualAmount"] == "123.4500"
    assert data["isInvestment"] is True
    assert household.status_code == 201, household.text
    assert household.json()["data"]["manualAmount"] == "0.0000"
    assert household.json()["data"]["isInvestment"] is False
    assert [item["id"] for item in items.json()["items"]] == [data["id"]]

    with _client_for(_actor(USER_A)) as client:
        updated = client.patch(
            f"/api/v1/asset-categories/{data['id']}",
            json={"manualAmount": "200.0000", "isInvestment": False, "version": 1},
        )
        archived = client.post(f"/api/v1/asset-categories/{data['id']}/archive")
        restored = client.post(f"/api/v1/asset-categories/{data['id']}/restore")

    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["manualAmount"] == "200.0000"
    assert updated.json()["data"]["isInvestment"] is False
    assert archived.status_code == 200
    assert archived.json()["data"]["recordStatus"] == "archived"
    assert restored.status_code == 200
    assert restored.json()["data"]["recordStatus"] == "active"


def test_household_asset_category_requires_active_membership() -> None:
    with _client_for(_actor(USER_INVITED, MembershipStatus.INVITED)) as client:
        denied = client.post(
            "/api/v1/asset-categories",
            json={
                "name": "Denied",
                "scopeType": "household",
                "householdId": HOUSEHOLD_AB,
                "currency": "RUB",
            },
        )

    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND_OR_NOT_ACCESSIBLE"
