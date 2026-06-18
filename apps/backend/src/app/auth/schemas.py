"""Auth/session/reset/invite code contracts.

The project is still scaffold-first, so these contracts use stdlib dataclasses
instead of depending on Pydantic before the backend dependency manifest exists.
FastAPI/Pydantic DTOs can wrap or replace them during router integration while
preserving the same neutral-response and transport semantics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Literal


class AuthTransport(StrEnum):
    PWA_COOKIE = "pwa_cookie"
    ANDROID_BEARER = "android_bearer"


class NeutralFlow(StrEnum):
    LOGIN_FAILURE = "login_failure"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    INVITE_REQUEST = "invite_request"


NEUTRAL_RESPONSE_MESSAGES: dict[NeutralFlow, str] = {
    NeutralFlow.LOGIN_FAILURE: "Unable to complete login with the supplied credentials.",
    NeutralFlow.PASSWORD_RESET_REQUEST: (
        "If the request can be processed, password reset instructions will be sent."
    ),
    NeutralFlow.INVITE_REQUEST: "If the invite can be processed, the recipient will be notified.",
}


@dataclass(frozen=True, slots=True)
class NeutralPublicResponse:
    """Public response body for account-neutral auth flows."""

    flow: NeutralFlow
    message: str
    status: Literal["accepted", "denied"] = "accepted"
    request_id: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        body = asdict(self)
        body["flow"] = self.flow.value
        return body


@dataclass(frozen=True, slots=True)
class LoginRequest:
    """Login boundary contract.

    Password plaintext exists only in the request boundary object and must not
    be logged or copied into audit details.
    """

    email: str
    password: str
    transport: AuthTransport


@dataclass(frozen=True, slots=True)
class RegistrationRequest:
    """Registration boundary contract.

    Password plaintext exists only in the request boundary object and must not
    be logged or copied into audit details.
    """

    email: str
    password: str
    display_name: str | None
    transport: AuthTransport


@dataclass(frozen=True, slots=True)
class PasswordResetRequest:
    email: str
    transport: AuthTransport | None = None


@dataclass(frozen=True, slots=True)
class PasswordResetConfirmRequest:
    """Password reset confirmation boundary contract.

    ``reset_token`` and ``new_password`` are plaintext request-boundary fields.
    Storage interfaces accept only approved token/password hashes.
    """

    reset_token: str
    new_password: str
    transport: AuthTransport


@dataclass(frozen=True, slots=True)
class InviteRequest:
    household_id: str
    recipient_email: str
    requested_by_user_id: str


@dataclass(frozen=True, slots=True)
class PwaCookieCsrfContract:
    transport: AuthTransport = AuthTransport.PWA_COOKIE
    cookie_name: str = "__Host-finance_session"
    cookie_http_only: bool = True
    cookie_secure: bool = True
    cookie_same_site: Literal["lax", "strict"] = "lax"
    csrf_cookie_name: str = "finance_csrf"
    csrf_cookie_http_only: bool = False
    csrf_header_name: str = "X-CSRF-Token"
    csrf_bound_to_session: bool = True
    csrf_rotates_on: tuple[str, ...] = ("login", "logout", "password_reset")
    cache_control: str = "private, no-store"


@dataclass(frozen=True, slots=True)
class AndroidBearerRefreshContract:
    transport: AuthTransport = AuthTransport.ANDROID_BEARER
    authorization_scheme: str = "Bearer"
    access_token_format: str = "opaque"
    access_token_storage: str = "memory_preferred"
    refresh_token_storage: str = "android_keystore_backed_secure_storage"
    refresh_token_rotation_required: bool = True
    server_revocation_required: bool = True


@dataclass(frozen=True, slots=True)
class SessionTransportContracts:
    pwa: PwaCookieCsrfContract = PwaCookieCsrfContract()
    android: AndroidBearerRefreshContract = AndroidBearerRefreshContract()
