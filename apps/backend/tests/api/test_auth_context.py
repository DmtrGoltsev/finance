from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_context import (
    AUTHENTICATION_REQUIRED_DETAIL,
    CurrentActor,
    fixed_actor_provider_for_tests,
    provide_actor,
)
from app.authz import Actor, Membership, MembershipStatus
from app.main import create_app
from tests.api.route_introspection import iter_api_routes


def _service_app() -> FastAPI:
    app = FastAPI()

    @app.get("/private")
    async def private_route(actor: CurrentActor) -> dict[str, object]:
        return {
            "user_id": actor.user_id,
            "memberships": [
                {
                    "household_id": membership.household_id,
                    "status": membership.status.value,
                }
                for membership in actor.memberships
            ],
        }

    return app


def test_default_auth_context_denies_without_provider_override() -> None:
    app = _service_app()

    with TestClient(app) as client:
        response = client.get(
            "/private",
            headers={"Authorization": "Bearer raw-token-must-not-echo"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": AUTHENTICATION_REQUIRED_DETAIL}
    public_body = response.text.lower()
    assert "raw-token-must-not-echo" not in public_body
    assert "bearer" not in public_body
    assert "session" not in public_body


def test_explicit_provider_override_allows_authenticated_actor() -> None:
    app = _service_app()
    user_id = str(uuid4())
    household_id = str(uuid4())
    actor = Actor(
        user_id=user_id,
        memberships=(
            Membership(
                user_id=user_id,
                household_id=household_id,
                status=MembershipStatus.ACTIVE,
            ),
        ),
    )
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)

    with TestClient(app) as client:
        response = client.get("/private")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user_id,
        "memberships": [
            {
                "household_id": household_id,
                "status": MembershipStatus.ACTIVE.value,
            },
        ],
    }


def test_invited_and_former_actors_can_be_represented_by_override() -> None:
    app = _service_app()
    user_id = str(uuid4())
    invited_household_id = str(uuid4())
    old_household_id = str(uuid4())
    actor = Actor(
        user_id=user_id,
        memberships=(
            Membership(
                user_id=user_id,
                household_id=invited_household_id,
                status=MembershipStatus.INVITED,
            ),
            Membership(
                user_id=user_id,
                household_id=old_household_id,
                status=MembershipStatus.LEFT,
            ),
        ),
    )
    app.dependency_overrides[provide_actor] = fixed_actor_provider_for_tests(actor)

    with TestClient(app) as client:
        response = client.get("/private")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user_id,
        "memberships": [
            {
                "household_id": invited_household_id,
                "status": MembershipStatus.INVITED.value,
            },
            {
                "household_id": old_household_id,
                "status": MembershipStatus.LEFT.value,
            },
        ],
    }


def test_auth_session_routes_are_mounted_but_default_deny_without_runtime() -> None:
    app = create_app()
    mounted_paths = {route.path for route in iter_api_routes(app.routes) if hasattr(route, "path")}

    assert "/api/v1/sessions" in mounted_paths
    assert "/api/v1/sessions/current" in mounted_paths
    assert "/api/v1/password-resets" not in mounted_paths
    assert "/api/v1/invites/requests" not in mounted_paths

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "email": "owner@example.test",
                "password": "not-a-real-password",
            },
        )

    assert response.status_code == 401
    assert response.json()["flow"] == "login_failure"
