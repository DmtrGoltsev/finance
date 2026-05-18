import pytest

from app.config import Settings
from app.db.session import (
    DatabaseRuntimeConfigurationError,
    accounts_categories_repository_mode,
)


def _settings(
    *,
    environment: str = "local",
    database_url: str = "postgresql+asyncpg://finance_local@localhost:5432/finance_dev",
    repository_mode: str = "auto",
    migration_policy: str = "none",
) -> Settings:
    return Settings(
        environment=environment,
        database_url=database_url,
        accounts_categories_repository_mode=repository_mode,
        database_migration_policy=migration_policy,
        _env_file=None,
    )


def test_local_and_test_default_repository_mode_stays_memory() -> None:
    assert accounts_categories_repository_mode(_settings(environment="local")) == "memory"
    assert accounts_categories_repository_mode(_settings(environment="test")) == "memory"


def test_tests_can_opt_into_memory_or_sqlite_db_explicitly() -> None:
    sqlite_settings = _settings(
        environment="test",
        database_url="sqlite+pysqlite:///runtime-test.sqlite",
        repository_mode="db",
    )

    memory_settings = _settings(environment="test", repository_mode="memory")

    assert accounts_categories_repository_mode(memory_settings) == "memory"
    assert accounts_categories_repository_mode(sqlite_settings) == "db"


def test_production_like_auto_requires_explicit_database_url() -> None:
    with pytest.raises(DatabaseRuntimeConfigurationError, match="DATABASE_URL"):
        accounts_categories_repository_mode(_settings(environment="production"))


def test_production_like_cannot_force_memory_repository() -> None:
    with pytest.raises(DatabaseRuntimeConfigurationError, match="DB-backed"):
        accounts_categories_repository_mode(
            _settings(
                environment="staging",
                database_url="postgresql+asyncpg://finance@db.example.test:5432/finance",
                repository_mode="memory",
                migration_policy="external",
            )
        )


def test_production_like_db_requires_external_migration_policy() -> None:
    with pytest.raises(DatabaseRuntimeConfigurationError, match="MIGRATION_POLICY=external"):
        accounts_categories_repository_mode(
            _settings(
                environment="production",
                database_url="postgresql+asyncpg://finance@db.example.test:5432/finance",
                repository_mode="db",
            )
        )


def test_production_like_db_requires_postgresql_url() -> None:
    with pytest.raises(DatabaseRuntimeConfigurationError, match="PostgreSQL"):
        accounts_categories_repository_mode(
            _settings(
                environment="production",
                database_url="sqlite+pysqlite:///not-production.sqlite",
                repository_mode="db",
                migration_policy="external",
            )
        )


def test_production_like_default_resolves_to_db_when_gates_are_explicit() -> None:
    settings = _settings(
        environment="production",
        database_url="postgresql+asyncpg://finance@db.example.test:5432/finance",
        migration_policy="external",
    )

    assert accounts_categories_repository_mode(settings) == "db"


def test_invalid_repository_and_migration_policy_values_fail_fast() -> None:
    with pytest.raises(RuntimeError, match="ACCOUNTS_CATEGORIES_REPOSITORY_MODE"):
        accounts_categories_repository_mode(_settings(repository_mode="sidecar"))

    with pytest.raises(RuntimeError, match="DATABASE_MIGRATION_POLICY"):
        accounts_categories_repository_mode(
            _settings(
                environment="production",
                database_url="postgresql+asyncpg://finance@db.example.test:5432/finance",
                repository_mode="db",
                migration_policy="auto",
            )
        )
