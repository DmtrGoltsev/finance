from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HmacVerification:
    timestamp: int
    nonce: str


class HmacVerificationError(ValueError):
    pass


def sign_callback(*, secret: str, timestamp: int, nonce: str, body: bytes) -> str:
    payload = str(timestamp).encode() + b"." + nonce.encode() + b"." + body
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_callback(
    *,
    secret: str | None,
    timestamp_text: str | None,
    nonce: str | None,
    signature: str | None,
    body: bytes,
    now_epoch: int | None = None,
    max_clock_skew_seconds: int = 300,
) -> HmacVerification:
    if not secret:
        raise HmacVerificationError("callback secret is not configured")
    if not timestamp_text or not nonce or not signature:
        raise HmacVerificationError("missing callback authentication headers")
    if len(nonce) < 16 or len(nonce) > 128:
        raise HmacVerificationError("invalid callback nonce")
    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise HmacVerificationError("invalid callback timestamp") from exc
    current = int(time.time()) if now_epoch is None else now_epoch
    if abs(current - timestamp) > max_clock_skew_seconds:
        raise HmacVerificationError("callback timestamp outside allowed window")
    expected = sign_callback(secret=secret, timestamp=timestamp, nonce=nonce, body=body)
    if not hmac.compare_digest(expected, signature.casefold()):
        raise HmacVerificationError("invalid callback signature")
    return HmacVerification(timestamp=timestamp, nonce=nonce)
