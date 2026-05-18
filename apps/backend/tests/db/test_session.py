from sqlalchemy.engine import make_url

from app.db.session import sync_database_url


def test_sync_database_url_preserves_postgresql_password() -> None:
    database_url = (
        "postgresql+asyncpg://finance_app:dummy-password@127.0.0.1:5432/finance"
    )

    sync_url = sync_database_url(database_url)
    parsed_url = make_url(sync_url)

    assert parsed_url.drivername == "postgresql+psycopg"
    assert parsed_url.password == "dummy-password"
    assert "dummy-password" in sync_url
    assert "***" not in sync_url
