"""Auth security primitives and release-gated helpers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol

from .schemas import (
    AndroidBearerRefreshContract,
    IosBearerRefreshContract,
    PwaCookieCsrfContract,
    SessionTransportContracts,
)

TOKEN_LOG_REDACTION = "[REDACTED_AUTH_TOKEN]"
MIN_TOKEN_BYTES = 32
MIN_TOKEN_HASH_SECRET_BYTES = 32
TOKEN_HASH_PREFIX = "hmac-sha256:v1:"
MIN_PASSWORD_SALT_BYTES = 16
MIN_PASSWORD_PBKDF2_ITERATIONS = 210_000
PASSWORD_HASH_SCHEME = "pbkdf2-sha256"
PASSWORD_HASH_VERSION = "v1"
PASSWORD_HASH_PREFIX = f"{PASSWORD_HASH_SCHEME}:{PASSWORD_HASH_VERSION}:"


class AuthSecurityConfigurationError(ValueError):
    """Raised when auth primitives are configured below the release baseline."""


class TokenHashingBackend(Protocol):
    """Approved one-way hashing backend for random auth tokens."""

    def hash_token(self, token_plaintext: str) -> str:
        """Return a storage-safe hash for a plaintext token."""

    def verify_token(self, token_plaintext: str, stored_token_hash: str) -> bool:
        """Verify a plaintext boundary token against a stored token hash."""


class PasswordHashingBackend(Protocol):
    """Approved password hashing backend for request-boundary passwords."""

    def hash_password(self, password_plaintext: str) -> str:
        """Return a storage-safe password hash."""

    def verify_password(self, password_plaintext: str, stored_password_hash: str) -> bool:
        """Verify a plaintext boundary password against a stored hash."""


@dataclass(frozen=True, slots=True)
class RandomTokenFactory:
    """Generate opaque auth tokens with stdlib CSPRNG entropy."""

    token_bytes: int = MIN_TOKEN_BYTES

    def __post_init__(self) -> None:
        if self.token_bytes < MIN_TOKEN_BYTES:
            raise AuthSecurityConfigurationError("auth tokens require at least 32 random bytes")

    def create_token(self) -> str:
        return secrets.token_urlsafe(self.token_bytes)


@dataclass(frozen=True, slots=True)
class HmacSha256TokenHashingBackend:
    """Storage-safe keyed hash backend for random opaque auth tokens.

    This is suitable for high-entropy random tokens, not user passwords.
    Password hashing still requires a dedicated password-hashing backend.
    """

    secret: bytes | str
    context: str = "finance-auth-token"

    def __post_init__(self) -> None:
        secret_bytes = _secret_bytes(self.secret)
        if len(secret_bytes) < MIN_TOKEN_HASH_SECRET_BYTES:
            raise AuthSecurityConfigurationError(
                "token hash secret requires at least 32 bytes from deployment secrets"
            )
        if not self.context:
            raise AuthSecurityConfigurationError("token hash context is required")

    def hash_token(self, token_plaintext: str) -> str:
        token_bytes = _token_bytes(token_plaintext)
        digest = hmac.new(
            _secret_bytes(self.secret),
            self.context.encode("utf-8") + b"\0" + token_bytes,
            hashlib.sha256,
        ).digest()
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"{TOKEN_HASH_PREFIX}{encoded}"

    def verify_token(self, token_plaintext: str, stored_token_hash: str) -> bool:
        if not stored_token_hash.startswith(TOKEN_HASH_PREFIX):
            return False
        return hmac.compare_digest(
            self.hash_token(token_plaintext),
            stored_token_hash,
        )


@dataclass(frozen=True, slots=True)
class Pbkdf2Sha256PasswordHashingBackend:
    """Stdlib password hashing primitive for the MVP auth foundation.

    This is intentionally explicit and swappable. A future release-hardening
    worker can replace it with an Argon2id/bcrypt backend without changing the
    credential/session service contracts.
    """

    iterations: int = MIN_PASSWORD_PBKDF2_ITERATIONS
    salt_bytes: int = MIN_PASSWORD_SALT_BYTES

    def __post_init__(self) -> None:
        if self.iterations < MIN_PASSWORD_PBKDF2_ITERATIONS:
            raise AuthSecurityConfigurationError(
                "password hashing requires at least 210000 PBKDF2 iterations"
            )
        if self.salt_bytes < MIN_PASSWORD_SALT_BYTES:
            raise AuthSecurityConfigurationError(
                "password hashing requires at least 16 random salt bytes"
            )

    def hash_password(self, password_plaintext: str) -> str:
        password_bytes = _password_bytes(password_plaintext)
        salt = secrets.token_bytes(self.salt_bytes)
        digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, self.iterations)
        return (
            f"{PASSWORD_HASH_PREFIX}{self.iterations}:"
            f"{_base64_urlsafe_no_padding(salt)}:{_base64_urlsafe_no_padding(digest)}"
        )

    def verify_password(self, password_plaintext: str, stored_password_hash: str) -> bool:
        try:
            scheme, version, iterations_text, salt_text, digest_text = (
                stored_password_hash.split(":", 4)
            )
            if scheme != PASSWORD_HASH_SCHEME or version != PASSWORD_HASH_VERSION:
                return False
            iterations = int(iterations_text)
            if iterations < MIN_PASSWORD_PBKDF2_ITERATIONS:
                return False
            salt = _base64_urlsafe_decode(salt_text)
            stored_digest = _base64_urlsafe_decode(digest_text)
            candidate_digest = hashlib.pbkdf2_hmac(
                "sha256",
                _password_bytes(password_plaintext),
                salt,
                iterations,
            )
        except (TypeError, ValueError, binascii.Error):
            return False

        return hmac.compare_digest(candidate_digest, stored_digest)


def session_transport_contracts() -> SessionTransportContracts:
    """Return PWA, Android, and iOS auth transport contracts."""

    return SessionTransportContracts(
        pwa=PwaCookieCsrfContract(),
        android=AndroidBearerRefreshContract(),
        ios=IosBearerRefreshContract(),
    )


def redact_token_for_log(value: object) -> str:
    """Return a constant marker instead of logging token-like values."""

    return TOKEN_LOG_REDACTION


def _secret_bytes(secret: bytes | str) -> bytes:
    if isinstance(secret, str):
        return secret.encode("utf-8")
    return secret


def _token_bytes(token_plaintext: str) -> bytes:
    if not token_plaintext:
        raise ValueError("token plaintext is required")
    return token_plaintext.encode("utf-8")


def _password_bytes(password_plaintext: str) -> bytes:
    if not password_plaintext:
        raise ValueError("password plaintext is required")
    return password_plaintext.encode("utf-8")


def _base64_urlsafe_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64_urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
