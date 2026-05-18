"""Invite token lifecycle skeleton.

Release blockers before production:
- approved random token generation and hashing backend;
- one-time hashed-token storage with expiry/revocation;
- invite create/resend/accept/decline rate-limit backend;
- authz integration proving invite tokens do not grant shared financial access
  before active membership is committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .models import InviteTokenStorageRecord
from .schemas import InviteRequest, NeutralPublicResponse
from .service import AuthReleaseBlocker, neutral_invite_request_response


class InviteTokenStore(Protocol):
    """Storage interface for hashed invite tokens only."""

    def store_invite_token_hash(
        self,
        *,
        invite_id: str,
        invite_token_hash: str,
        expires_at: datetime,
    ) -> InviteTokenStorageRecord:
        """Persist a hashed invite token.

        The caller must never pass or persist the plaintext invite token here.
        """

    def consume_invite_token_hash(self, *, invite_token_hash: str, consumed_at: datetime) -> None:
        """Mark a hashed invite token as consumed after verification."""


@dataclass(slots=True)
class InviteTokenService:
    store: InviteTokenStore | None = None

    def request_invite(self, request: InviteRequest, request_id: str | None = None) -> NeutralPublicResponse:
        """Return a neutral invite request response.

        The eventual implementation may create/resend an invite only after
        authz, rate-limit, storage, and delivery checks. The public response
        remains neutral so it does not disclose recipient/account state.
        """

        return neutral_invite_request_response(request_id=request_id)

    def issue_invite_token(self, *, invite_id: str) -> InviteTokenStorageRecord:
        """Issue and store an invite token hash.

        TODO(W2-04 release blocker): generate a random plaintext token at the
        delivery boundary, hash it with the approved backend, store only the
        hash, and ensure neither plaintext nor hash reaches logs.
        """

        raise AuthReleaseBlocker(
            "Invite token issuance requires approved token generation, hashing, "
            "storage, delivery, and rate-limit backends."
        )

    def accept_or_decline_with_token(self, *, invite_token_plaintext: str) -> None:
        """Verify a plaintext invite token at the request boundary only."""

        raise AuthReleaseBlocker(
            "Invite token verification requires hashed-token lookup, one-time "
            "consume semantics, expiry checks, and membership/authz integration."
        )
