"""Mounted FastAPI routes for the MVP auth/session foundation."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.auth_context import (
    CurrentActor,
    bearer_token_from_authorization_header,
    cookie_session_token_from_request,
)
from app.api.error_contract import request_id_for
from app.auth.cookies import clear_pwa_auth_cookies, set_pwa_auth_cookies
from app.authz import Actor
from app.config import get_settings

from .runtime import AuthSessionService, get_auth_session_service
from .schemas import AuthTransport, LoginRequest
from .service import neutral_login_failure_response

LOGIN_SESSION_ROUTE = "/sessions"
CURRENT_SESSION_ROUTE = "/sessions/current"
PASSWORD_RESET_REQUEST_ROUTE = "/password-resets"
INVITE_REQUEST_ROUTE = "/invites/requests"
NO_STORE_HEADERS = {"Cache-Control": "private, no-store"}


class LoginSessionRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    transport: AuthTransport = AuthTransport.ANDROID_BEARER


class ActorMembershipResponse(BaseModel):
    householdId: str
    status: str


class ActorContextResponse(BaseModel):
    userId: str
    sessionId: str | None = None
    memberships: list[ActorMembershipResponse]


class BearerSessionResponse(BaseModel):
    tokenType: Literal["Bearer"] = "Bearer"
    accessToken: str
    expiresAt: str
    actor: ActorContextResponse


class PwaCookieSessionResponse(BaseModel):
    transport: Literal["pwa_cookie"] = "pwa_cookie"
    csrfToken: str
    expiresAt: str
    actor: ActorContextResponse


router = APIRouter(tags=["auth-session"], include_in_schema=False)
AuthSessionDependency = Annotated[AuthSessionService, Depends(get_auth_session_service)]


@router.post(LOGIN_SESSION_ROUTE, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: LoginSessionRequest,
    request: Request,
    auth_service: AuthSessionDependency,
) -> JSONResponse:
    """Verify credentials and issue an opaque Android bearer or PWA cookie session."""

    result = auth_service.login(
        LoginRequest(
            email=payload.email,
            password=payload.password,
            transport=payload.transport,
        ),
        request_id=request_id_for(request),
    )
    if not result.authenticated or result.issued_session is None or result.actor is None:
        neutral = neutral_login_failure_response(request_id=request_id_for(request))
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=neutral.to_public_dict(),
            headers=NO_STORE_HEADERS,
        )

    if payload.transport == AuthTransport.PWA_COOKIE:
        response_body = PwaCookieSessionResponse(
            csrfToken=result.issued_session.csrf_token or "",
            expiresAt=result.issued_session.storage_record.expires_at.isoformat(),
            actor=actor_context_response(result.actor),
        )
        response = JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=response_body.model_dump(),
            headers=NO_STORE_HEADERS,
        )
        set_pwa_auth_cookies(
            response,
            issued=result.issued_session,
            settings=get_settings(),
        )
        return response

    response_body = BearerSessionResponse(
        accessToken=result.issued_session.session_token or "",
        expiresAt=result.issued_session.storage_record.expires_at.isoformat(),
        actor=actor_context_response(result.actor),
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response_body.model_dump(),
        headers=NO_STORE_HEADERS,
    )


@router.get(CURRENT_SESSION_ROUTE)
async def get_current_session(actor: CurrentActor) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"actor": actor_context_response(actor).model_dump()},
        headers=NO_STORE_HEADERS,
    )


@router.delete(CURRENT_SESSION_ROUTE, status_code=status.HTTP_204_NO_CONTENT)
async def revoke_current_session(
    request: Request,
    actor: CurrentActor,
    auth_service: AuthSessionDependency,
) -> Response:
    del actor
    bearer_token = bearer_token_from_authorization_header(request.headers.get("authorization"))
    cookie_session_token = cookie_session_token_from_request(request)
    if bearer_token is not None:
        auth_service.revoke_bearer_token(bearer_token)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=NO_STORE_HEADERS)

    auth_service.revoke_cookie_session(cookie_session_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT, headers=NO_STORE_HEADERS)
    clear_pwa_auth_cookies(response, settings=get_settings())
    return response


def actor_context_response(actor: Actor) -> ActorContextResponse:
    return ActorContextResponse(
        userId=actor.user_id or "",
        sessionId=actor.session_id,
        memberships=[
            ActorMembershipResponse(
                householdId=membership.household_id,
                status=membership.status.value,
            )
            for membership in actor.memberships
        ],
    )
