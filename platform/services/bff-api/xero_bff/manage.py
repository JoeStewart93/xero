from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from xero_bff.auth import ensure_seed_users
from xero_bff.config import get_settings

BFF_ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    config = Config(str(BFF_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BFF_ROOT / "alembic"))
    config.set_main_option("version_table", "bff_alembic_version")
    return config


def migrate() -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def seed() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    created = ensure_seed_users(settings)
    print(f"Seeded default users: {', '.join(created)}" if created else "Default users already exist")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Xero BFF database state.")
    parser.add_argument("command", choices=("migrate", "seed"))
    args = parser.parse_args()
    if args.command == "migrate":
        return migrate()
    return seed()


if __name__ == "__main__":
    raise SystemExit(main())
