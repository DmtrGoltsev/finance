"""Auth audit/logging guardrails.

Release blocker: no auth audit event may include plaintext passwords, session
tokens, refresh tokens, CSRF values, invite/reset tokens, token hashes, or raw
request/response bodies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class AuthAuditAction(StrEnum):
    LOGIN_ATTEMPT = "login_attempt"
    LOGOUT = "logout"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_CONFIRM = "password_reset_confirm"
    INVITE_CREATE = "invite_create"
    INVITE_RESEND = "invite_resend"
    INVITE_TOKEN_ATTEMPT = "invite_token_attempt"
    SESSION_REVOKE = "session_revoke"


class AuthAuditResult(StrEnum):
    ACCEPTED_NEUTRAL = "accepted_neutral"
    SUCCEEDED = "succeeded"
    DENIED_NEUTRAL = "denied_neutral"
    RATE_LIMITED = "rate_limited"
    RELEASE_BLOCKED = "release_blocked"


FORBIDDEN_AUTH_AUDIT_FIELD_FRAGMENTS = (
    "authorization",
    "cookie",
    "csrf",
    "password",
    "secret",
    "session",
    "token",
    "token_hash",
)

REDACTED_AUTH_AUDIT_VALUE = "[REDACTED_AUTH_SECRET]"


@dataclass(frozen=True, slots=True)
class AuthAuditNote:
    """Minimal auth audit event shape safe for future structured logging."""

    action: AuthAuditAction
    result: AuthAuditResult
    request_id: str | None = None
    actor_user_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    scope_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def safe_details(self) -> dict[str, Any]:
        """Return details with auth secrets removed before logging."""

        return redact_auth_audit_details(self.details)


def is_forbidden_auth_audit_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in FORBIDDEN_AUTH_AUDIT_FIELD_FRAGMENTS)


def redact_auth_audit_details(details: Mapping[str, Any]) -> dict[str, Any]:
    """Remove or redact auth-sensitive values from audit payloads.

    Token hashes are treated as sensitive too; they are storage-only values and
    should not appear in logs or audit trails unless a later security review
    explicitly approves a one-way fingerprint format.
    """

    redacted: dict[str, Any] = {}
    for key, value in details.items():
        if is_forbidden_auth_audit_key(key):
            redacted[key] = REDACTED_AUTH_AUDIT_VALUE
        elif isinstance(value, Mapping):
            redacted[key] = redact_auth_audit_details(value)
        else:
            redacted[key] = value
    return redacted
