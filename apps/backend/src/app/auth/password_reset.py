"""Password reset token lifecycle skeleton.

Release blockers before production:
- approved password hashing and reset-token hashing backends;
- one-time hashed reset-token storage with expiry/replay protection;
- old-session revocation after successful reset;
- neutral request behavior and rate-limit evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .models import PasswordResetTokenStorageRecord
from .schemas import NeutralPublicResponse, PasswordResetConfirmRequest, PasswordResetRequest
from .service import AuthReleaseBlocker, neutral_password_reset_request_response


class PasswordResetTokenStore(Protocol):
    """Storage interface for hashed reset tokens only."""

    def store_reset_token_hash(
        self,
        *,
        user_id: str,
        reset_token_hash: str,
        requested_email_hash: str,
        expires_at: datetime,
    ) -> PasswordResetTokenStorageRecord:
        """Persist a reset token hash.

        The caller must never pass or persist the plaintext reset token here.
        """

    def consume_reset_token_hash(self, *, reset_token_hash: str, consumed_at: datetime) -> None:
        """Mark a hashed reset token as consumed after successful reset."""


@dataclass(slots=True)
class PasswordResetService:
    store: PasswordResetTokenStore | None = None

    def request_reset(
        self,
        request: PasswordResetRequest,
        request_id: str | None = None,
    ) -> NeutralPublicResponse:
        """Return a neutral password reset request response.

        Future implementation must perform rate-limit checks, privately resolve
        the account if it exists, and send a reset notice without changing the
        public response for missing, disabled, or rate-limited identities.
        """

        return neutral_password_reset_request_response(request_id=request_id)

    def issue_reset_token(self, *, user_id: str, requested_email: str) -> PasswordResetTokenStorageRecord:
        """Issue and store a password reset token hash.

        TODO(W2-04 release blocker): generate a random plaintext token at the
        delivery boundary, hash it with the approved backend, store only the
        hash, and ensure neither plaintext nor hash reaches logs.
        """

        raise AuthReleaseBlocker(
            "Password reset token issuance requires approved token generation, "
            "hashing, storage, mail delivery, and rate-limit backends."
        )

    def confirm_reset(self, request: PasswordResetConfirmRequest) -> None:
        """Verify token, update password hash, and revoke old sessions."""

        raise AuthReleaseBlocker(
            "Password reset confirmation requires hashed-token verification, "
            "password hashing, one-time consume semantics, and session revocation."
        )
