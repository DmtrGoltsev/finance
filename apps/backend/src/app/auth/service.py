"""Auth foundation service helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    NEUTRAL_RESPONSE_MESSAGES,
    InviteRequest,
    LoginRequest,
    NeutralFlow,
    NeutralPublicResponse,
    PasswordResetRequest,
)


class AuthReleaseBlocker(RuntimeError):
    """Raised when skeleton code reaches unreleased auth functionality."""


RELEASE_BLOCKERS: tuple[str, ...] = (
    "Deployment token hash secret must be wired for non-test runtime login.",
    "Session/reset/invite token persistence is not integrated with the production DB store.",
    "Rate-limit counters are config-only and not enforced by a backend.",
    "CSRF verification and rotation are not wired to session storage.",
    "Audit/log sinks must prove no plaintext tokens, token hashes, passwords, "
    "or secrets are emitted.",
    "PWA cookie+CSRF, refresh-token rotation, and logout-all are not release-ready.",
)


def neutral_response_for(
    flow: NeutralFlow | str,
    request_id: str | None = None,
) -> NeutralPublicResponse:
    """Build a documented neutral response for public auth request flows."""

    normalized_flow = NeutralFlow(flow)
    status = "denied" if normalized_flow is NeutralFlow.LOGIN_FAILURE else "accepted"
    return NeutralPublicResponse(
        flow=normalized_flow,
        message=NEUTRAL_RESPONSE_MESSAGES[normalized_flow],
        status=status,
        request_id=request_id,
    )


def neutral_login_failure_response(request_id: str | None = None) -> NeutralPublicResponse:
    """Login failure body that does not confirm whether the account exists."""

    return neutral_response_for(NeutralFlow.LOGIN_FAILURE, request_id=request_id)


def neutral_password_reset_request_response(request_id: str | None = None) -> NeutralPublicResponse:
    """Password-reset request body that does not confirm whether email exists."""

    return neutral_response_for(NeutralFlow.PASSWORD_RESET_REQUEST, request_id=request_id)


def neutral_invite_request_response(request_id: str | None = None) -> NeutralPublicResponse:
    """Invite request body that does not disclose recipient account/invite state."""

    return neutral_response_for(NeutralFlow.INVITE_REQUEST, request_id=request_id)


@dataclass(slots=True)
class AuthFoundationService:
    """Coordinator facade for future auth implementation."""

    def login(self, request: LoginRequest, request_id: str | None = None) -> NeutralPublicResponse:
        """Return a neutral login failure until credential/session backends exist."""

        return neutral_login_failure_response(request_id=request_id)

    def request_password_reset(
        self,
        request: PasswordResetRequest,
        request_id: str | None = None,
    ) -> NeutralPublicResponse:
        """Return the neutral password reset response for all public outcomes."""

        return neutral_password_reset_request_response(request_id=request_id)

    def request_invite(
        self,
        request: InviteRequest,
        request_id: str | None = None,
    ) -> NeutralPublicResponse:
        """Return the neutral invite response for all public outcomes."""

        return neutral_invite_request_response(request_id=request_id)

    def issue_session(self) -> None:
        raise AuthReleaseBlocker(
            "Session issuance requires credential verification, storage, token "
            "hashing, CSRF rotation, and rate-limit enforcement."
        )
