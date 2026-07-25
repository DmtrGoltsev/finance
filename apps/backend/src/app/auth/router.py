"""Mounted FastAPI routes for the MVP auth/session foundation."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.auth_context import (
    CurrentActor,
    bearer_token_from_authorization_header,
    cookie_session_token_from_request,
)
from app.api.error_contract import error_response, request_id_for
from app.auth.cookies import clear_pwa_auth_cookies, set_pwa_auth_cookies
from app.auth.rate_limits import (
    InMemoryRateLimiter,
    RateLimitBucket,
    RateLimitKey,
    auth_rate_limit_identity_for_email,
    auth_rate_limit_identity_for_ip,
)
from app.authz import Actor
from app.config import get_settings

from .runtime import AuthSessionService, get_auth_session_service
from .schemas import AuthTransport, LoginRequest, RegistrationRequest
from .service import neutral_login_failure_response

USER_REGISTRATION_ROUTE = "/users"
LOGIN_SESSION_ROUTE = "/sessions"
REFRESH_SESSION_ROUTE = "/sessions/refresh"
CURRENT_SESSION_ROUTE = "/sessions/current"
PASSWORD_RESET_REQUEST_ROUTE = "/password-resets"
INVITE_REQUEST_ROUTE = "/invites/requests"
NO_STORE_HEADERS = {"Cache-Control": "private, no-store"}
REGISTRATION_UNAVAILABLE_MESSAGE = "User registration is not available."
REGISTRATION_ACCEPTED_MESSAGE = "If the request can be processed, registration will continue."
RATE_LIMIT_MESSAGE = "Too many requests."


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class LoginSessionRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    transport: AuthTransport = AuthTransport.ANDROID_BEARER
    device_name: str | None = Field(default=None, min_length=1, max_length=120)


class UserRegistrationRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    transport: AuthTransport = AuthTransport.ANDROID_BEARER
    device_name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        local, separator, domain = email.partition("@")
        if (
            not separator
            or not local
            or not domain
            or "@" in domain
            or any(character.isspace() for character in email)
            or "." not in domain
        ):
            raise ValueError("invalid email")
        return email

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("invalid password")
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class RefreshSessionRequest(ApiModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


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
    refreshToken: str
    expiresAt: str
    actor: ActorContextResponse


class PwaCookieSessionResponse(BaseModel):
    transport: Literal["pwa_cookie"] = "pwa_cookie"
    csrfToken: str
    expiresAt: str
    actor: ActorContextResponse


class RegistrationAcceptedResponse(BaseModel):
    registrationAccepted: Literal[True] = True
    message: str
    requestId: str


router = APIRouter(tags=["auth-session"], include_in_schema=False)
AuthSessionDependency = Annotated[AuthSessionService, Depends(get_auth_session_service)]


@router.post(LOGIN_SESSION_ROUTE, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: LoginSessionRequest,
    request: Request,
    auth_service: AuthSessionDependency,
) -> JSONResponse:
    """Verify credentials and issue an opaque Android bearer or PWA cookie session."""

    rate_limit_response = auth_rate_limit_response(
        request=request,
        buckets=(
            RateLimitBucket(
                RateLimitKey.LOGIN_IP_15M,
                auth_rate_limit_identity_for_ip(_client_host(request)),
            ),
            RateLimitBucket(
                RateLimitKey.LOGIN_ACCOUNT_15M,
                auth_rate_limit_identity_for_email(payload.email),
            ),
        ),
    )
    if rate_limit_response is not None:
        return rate_limit_response

    request_id = request_id_for(request)
    result = auth_service.login(
        LoginRequest(
            email=payload.email,
            password=payload.password,
            transport=payload.transport,
        ),
        request_id=request_id,
    )
    if not result.authenticated or result.issued_session is None or result.actor is None:
        neutral = neutral_login_failure_response(request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=neutral.to_public_dict(),
            headers=NO_STORE_HEADERS,
        )

    return session_creation_response(
        transport=payload.transport,
        issued=result.issued_session,
        actor=result.actor,
    )


@router.post(USER_REGISTRATION_ROUTE, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserRegistrationRequest,
    request: Request,
    auth_service: AuthSessionDependency,
) -> JSONResponse:
    """Create an active user and issue the first session for the requested transport."""

    request_id = request_id_for(request)
    rate_limit_response = auth_rate_limit_response(
        request=request,
        buckets=(
            RateLimitBucket(
                RateLimitKey.REGISTRATION_IP_HOUR,
                auth_rate_limit_identity_for_ip(_client_host(request)),
            ),
            RateLimitBucket(
                RateLimitKey.REGISTRATION_IP_DAY,
                auth_rate_limit_identity_for_ip(_client_host(request)),
            ),
            RateLimitBucket(
                RateLimitKey.REGISTRATION_EMAIL_HOUR,
                auth_rate_limit_identity_for_email(payload.email),
            ),
        ),
    )
    if rate_limit_response is not None:
        return rate_limit_response

    result = auth_service.register(
        RegistrationRequest(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            transport=payload.transport,
        ),
        request_id=request_id,
    )
    if result.conflict:
        return registration_accepted_response(request_id=request_id)
    if not result.registered or result.issued_session is None or result.actor is None:
        return error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="USER_REGISTRATION_UNAVAILABLE",
            message=REGISTRATION_UNAVAILABLE_MESSAGE,
            request_id=request_id,
        )

    return session_creation_response(
        transport=payload.transport,
        issued=result.issued_session,
        actor=result.actor,
    )


@router.post(REFRESH_SESSION_ROUTE, status_code=status.HTTP_200_OK)
async def refresh_session(
    payload: RefreshSessionRequest,
    request: Request,
    auth_service: AuthSessionDependency,
) -> JSONResponse:
    """Rotate Android bearer/refresh token material for an active session."""

    request_id = request_id_for(request)
    result = auth_service.refresh_android_session(
        payload.refresh_token,
        request_id=request_id,
    )
    if not result.refreshed or result.issued_session is None or result.actor is None:
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
            headers=NO_STORE_HEADERS,
        )

    return bearer_session_response(
        issued=result.issued_session,
        actor=result.actor,
        status_code=status.HTTP_200_OK,
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


def session_creation_response(
    *,
    transport: AuthTransport,
    issued,
    actor: Actor,
) -> JSONResponse:
    if transport == AuthTransport.PWA_COOKIE:
        response_body = PwaCookieSessionResponse(
            csrfToken=issued.csrf_token or "",
            expiresAt=issued.storage_record.expires_at.isoformat(),
            actor=actor_context_response(actor),
        )
        response = JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=response_body.model_dump(),
            headers=NO_STORE_HEADERS,
        )
        set_pwa_auth_cookies(
            response,
            issued=issued,
            settings=get_settings(),
        )
        return response

    return bearer_session_response(
        issued=issued,
        actor=actor,
        status_code=status.HTTP_201_CREATED,
    )


def bearer_session_response(
    *,
    issued,
    actor: Actor,
    status_code: int,
) -> JSONResponse:
    response_body = BearerSessionResponse(
        accessToken=issued.session_token or "",
        refreshToken=issued.refresh_token or "",
        expiresAt=issued.storage_record.expires_at.isoformat(),
        actor=actor_context_response(actor),
    )
    return JSONResponse(
        status_code=status_code,
        content=response_body.model_dump(),
        headers=NO_STORE_HEADERS,
    )


def auth_rate_limit_response(
    *,
    request: Request,
    buckets: tuple[RateLimitBucket, ...],
) -> JSONResponse | None:
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if not isinstance(limiter, InMemoryRateLimiter):
        return None

    decision = limiter.check_and_increment(buckets)
    if decision.allowed:
        return None

    headers = {**NO_STORE_HEADERS}
    if decision.retry_after_seconds is not None:
        headers["Retry-After"] = str(decision.retry_after_seconds)
    return error_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code="TOO_MANY_REQUESTS",
        message=RATE_LIMIT_MESSAGE,
        request_id=request_id_for(request),
        headers=headers,
    )


def registration_accepted_response(*, request_id: str) -> JSONResponse:
    response_body = RegistrationAcceptedResponse(
        message=REGISTRATION_ACCEPTED_MESSAGE,
        requestId=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=response_body.model_dump(),
        headers=NO_STORE_HEADERS,
    )


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client is not None else None
