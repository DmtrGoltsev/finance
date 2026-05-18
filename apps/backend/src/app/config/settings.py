from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FINANCE_BACKEND_",
        extra="ignore",
    )

    app_name: str = "Finance MVP Backend"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        description="Explicit browser origins allowed by CORS.",
    )
    dev_cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5173",
        ],
        description="Local-only PWA origins enabled outside production-like environments.",
    )
    database_url: str = Field(
        default="postgresql+asyncpg://finance_local@localhost:5432/finance_dev",
        description="Local development database URL. Override outside local dev.",
    )
    accounts_categories_repository_mode: str = Field(
        default="auto",
        description=(
            "Accounts/categories repository runtime: auto, memory, or db. "
            "Auto keeps local/test on memory and requires db for production-like environments."
        ),
    )
    database_migration_policy: str = Field(
        default="none",
        description=(
            "How schema migrations are applied before DB-backed runtime starts. "
            "Production-like runtime requires external migration orchestration."
        ),
    )
    auth_token_hash_secret: str | None = Field(
        default=None,
        description="Deployment secret for HMAC hashing opaque auth tokens.",
    )
    auth_bearer_session_ttl_seconds: int = Field(
        default=43_200,
        ge=300,
        description="Opaque bearer access/session token lifetime in seconds.",
    )
    auth_pwa_session_ttl_seconds: int = Field(
        default=43_200,
        ge=300,
        description="Opaque PWA cookie session token lifetime in seconds.",
    )
    auth_session_cookie_name: str = Field(
        default="__Host-finance_session",
        min_length=1,
        description="HttpOnly cookie name for the opaque PWA session token.",
    )
    auth_csrf_cookie_name: str = Field(
        default="finance_csrf",
        min_length=1,
        description="Readable cookie name carrying the CSRF token for browser clients.",
    )
    auth_csrf_header_name: str = Field(
        default="X-CSRF-Token",
        min_length=1,
        description="Header that must echo the CSRF cookie on unsafe cookie-auth requests.",
    )
    auth_cookie_path: str = Field(
        default="/",
        min_length=1,
        description="Path applied to auth cookies.",
    )
    auth_cookie_secure: bool = Field(
        default=True,
        description="Whether auth cookies are marked Secure.",
    )
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        description="SameSite value applied to PWA auth cookies.",
    )
    auth_password_pbkdf2_iterations: int = Field(
        default=210_000,
        ge=210_000,
        description="PBKDF2-SHA256 iterations for MVP password hash verification.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
