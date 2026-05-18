from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Literal

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

DEFAULT_DATABASE_URL = "postgresql+asyncpg://finance_local@localhost:5432/finance_dev"
PRODUCTION_LIKE_ENVIRONMENTS = frozenset({"prod", "production", "staging"})
REPOSITORY_MODES = frozenset({"auto", "memory", "db"})
MIGRATION_POLICIES = frozenset({"none", "external"})

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


class DatabaseRuntimeConfigurationError(RuntimeError):
    """Raised when DB-backed runtime would start without its required safety gates."""


def is_production_like_environment(environment: str) -> bool:
    return environment.strip().casefold() in PRODUCTION_LIKE_ENVIRONMENTS


def _normalized_setting(value: str, *, name: str, allowed: frozenset[str]) -> str:
    normalized = value.strip().casefold()
    if normalized not in allowed:
        raise RuntimeError(
            f"{name} must be one of: {', '.join(sorted(allowed))}"
        )
    return normalized


def database_url_is_explicit(settings: Settings) -> bool:
    return settings.database_url != DEFAULT_DATABASE_URL


def validate_database_runtime_policy(
    settings: Settings,
    *,
    repository_mode: Literal["memory", "db"],
) -> None:
    if not is_production_like_environment(settings.environment):
        return

    if repository_mode != "db":
        raise DatabaseRuntimeConfigurationError(
            "Production-like environments must use DB-backed accounts/categories repositories."
        )
    if not database_url_is_explicit(settings):
        raise DatabaseRuntimeConfigurationError(
            "Production-like DB runtime requires an explicit FINANCE_BACKEND_DATABASE_URL."
        )

    migration_policy = _normalized_setting(
        settings.database_migration_policy,
        name="FINANCE_BACKEND_DATABASE_MIGRATION_POLICY",
        allowed=MIGRATION_POLICIES,
    )
    if migration_policy != "external":
        raise DatabaseRuntimeConfigurationError(
            "Production-like DB runtime requires "
            "FINANCE_BACKEND_DATABASE_MIGRATION_POLICY=external."
        )

    database_url = make_url(settings.database_url)
    if database_url.get_backend_name() != "postgresql":
        raise DatabaseRuntimeConfigurationError(
            "Production-like DB runtime requires a PostgreSQL database URL."
        )


def accounts_categories_repository_mode(
    settings: Settings | None = None,
) -> Literal["memory", "db"]:
    app_settings = settings or get_settings()
    configured_mode = _normalized_setting(
        app_settings.accounts_categories_repository_mode,
        name="FINANCE_BACKEND_ACCOUNTS_CATEGORIES_REPOSITORY_MODE",
        allowed=REPOSITORY_MODES,
    )
    if configured_mode == "auto":
        repository_mode: Literal["memory", "db"] = (
            "db" if is_production_like_environment(app_settings.environment) else "memory"
        )
    elif configured_mode == "db":
        repository_mode = "db"
    else:
        repository_mode = "memory"
    validate_database_runtime_policy(app_settings, repository_mode=repository_mode)
    return repository_mode


def sync_database_url(database_url: str) -> str:
    """Return a sync SQLAlchemy URL for the accounts/categories runtime slice."""

    url = make_url(database_url)
    drivername = url.drivername
    if drivername == "postgresql+asyncpg":
        return url.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        )
    if drivername == "sqlite+aiosqlite":
        return str(url.set(drivername="sqlite+pysqlite"))
    return url.render_as_string(hide_password=False)


@lru_cache(maxsize=8)
def sync_engine_for_url(database_url: str) -> Engine:
    sync_url = sync_database_url(database_url)
    connect_args = {"check_same_thread": False} if sync_url.startswith("sqlite") else {}
    return create_engine(sync_url, pool_pre_ping=True, future=True, connect_args=connect_args)


def sync_session_factory_for_settings(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(
        bind=sync_engine_for_url(settings.database_url),
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def sync_session_scope(settings: Settings) -> Iterator[Session]:
    factory = sync_session_factory_for_settings(settings)
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
