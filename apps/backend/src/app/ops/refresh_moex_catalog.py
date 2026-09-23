"""Обновить серверный справочник выбранных инструментов из официального MOEX ISS."""

import argparse

from app.config import get_settings
from app.db.session import is_production_like_environment, sync_session_scope
from app.investments.moex_catalog import CatalogRefreshError, refresh_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secid", action="append", required=True)
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if is_production_like_environment(settings.environment) and not args.confirm_production:
        parser.error("Production catalog update requires --confirm-production")
    try:
        with sync_session_scope(settings) as session:
            count = refresh_catalog(session, args.secid)
    except CatalogRefreshError as error:
        parser.exit(1, f"Catalog refresh failed: {error}\n")
    print(f"Verified MOEX instruments: {count}")


if __name__ == "__main__":
    main()
