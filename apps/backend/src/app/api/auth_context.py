"""Authenticated actor dependency boundary for service routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.error_contract import request_id_for
from app.auth.cookies import CSRF_FAILURE_CODE, CSRF_FAILURE_MESSAGE, UNSAFE_METHODS
from app.auth.runtime import AuthSessionService, get_auth_session_service
from app.authz import Actor
from app.config import get_settings

AUTHENTICATION_REQUIRED_DETAIL = "authentication_required"
ActorProvider = Callable[[], Actor | None]


def bearer_token_from_authorization_header(value: str | None) -> str | None:
    """Parse an RFC6750-style bearer token without raising public errors."""

    if value is None:
        return None

    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None
    token = token.strip()
    if not token or " " in token:
        return None
    return token


def cookie_session_token_from_request(request: Request) -> str | None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie_name)
    if not token:
        return None
    return token


async def provide_actor(
    request: Request,
    auth_service: Annotated[AuthSessionService, Depends(get_auth_session_service)],
) -> Actor | None:
    """Resolve an actor from bearer auth first, then PWA cookie auth."""

    authorization_value = request.headers.get("authorization")
    bearer_token = bearer_token_from_authorization_header(authorization_value)
    if authorization_value is not None:
        if bearer_token is None:
            return None
        return auth_service.actor_for_bearer_token(
            bearer_token,
            request_id=request_id_for(request),
        )

    settings = get_settings()
    cookie_session_token = request.cookies.get(settings.auth_session_cookie_name)
    actor = auth_service.actor_for_cookie_session(
        cookie_session_token,
        request_id=request_id_for(request),
    )
    if actor is None:
        return None

    if request.method.upper() in UNSAFE_METHODS:
        csrf_header = request.headers.get(settings.auth_csrf_header_name)
        csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name)
        if (
            not csrf_header
            or not csrf_cookie
            or csrf_header != csrf_cookie
            or not auth_service.csrf_token_matches_cookie_session(
                session_token_plaintext=cookie_session_token,
                csrf_token_plaintext=csrf_header,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": CSRF_FAILURE_CODE,
                    "message": CSRF_FAILURE_MESSAGE,
                },
            )

    return actor


def _require_authenticated_actor(actor: Actor | None) -> Actor:
    if actor is None or not actor.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTHENTICATION_REQUIRED_DETAIL,
        )

    return actor


DefaultActorProviderResult = Annotated[Actor | None, Depends(provide_actor)]


async def require_authenticated_actor(actor: DefaultActorProviderResult) -> Actor:
    """Return the explicitly supplied actor or deny with a neutral 401."""

    return _require_authenticated_actor(actor)


def authenticated_actor_dependency(
    provider: ActorProvider = provide_actor,
) -> Callable[[Actor | None], Actor]:
    """Build a route dependency around an explicit actor provider."""

    async def dependency(actor: Annotated[Actor | None, Depends(provider)]) -> Actor:
        return _require_authenticated_actor(actor)

    return dependency


CurrentActor = Annotated[Actor, Depends(require_authenticated_actor)]


def fixed_actor_provider_for_tests(actor: Actor) -> ActorProvider:
    """Return a provider override for tests that need an explicit actor."""

    def override() -> Actor:
        return actor

    return override


__all__ = [
    "AUTHENTICATION_REQUIRED_DETAIL",
    "ActorProvider",
    "CurrentActor",
    "authenticated_actor_dependency",
    "bearer_token_from_authorization_header",
    "cookie_session_token_from_request",
    "fixed_actor_provider_for_tests",
    "provide_actor",
    "require_authenticated_actor",
]
