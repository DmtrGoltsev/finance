"""Cookie and CSRF helpers for browser session auth."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Response

from app.config import Settings

from .session_tokens import IssuedSession

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CSRF_FAILURE_CODE = "CSRF_TOKEN_INVALID"
CSRF_FAILURE_MESSAGE = "CSRF token missing or invalid."


def auth_cookie_max_age(issued: IssuedSession) -> int:
    expires_at = issued.storage_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return max(0, int((expires_at - datetime.now(UTC)).total_seconds()))


def set_pwa_auth_cookies(
    response: Response,
    *,
    issued: IssuedSession,
    settings: Settings,
) -> None:
    """Set the HttpOnly session cookie and readable CSRF cookie for a PWA login."""

    if issued.session_token is None or issued.csrf_token is None:
        return

    max_age = auth_cookie_max_age(issued)
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=issued.session_token,
        max_age=max_age,
        path=settings.auth_cookie_path,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=issued.csrf_token,
        max_age=max_age,
        path=settings.auth_cookie_path,
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite=settings.auth_cookie_samesite,
    )


def clear_pwa_auth_cookies(response: Response, *, settings: Settings) -> None:
    """Expire both PWA auth cookies using the configured cookie attributes."""

    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path=settings.auth_cookie_path,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
    response.delete_cookie(
        key=settings.auth_csrf_cookie_name,
        path=settings.auth_cookie_path,
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite=settings.auth_cookie_samesite,
    )
