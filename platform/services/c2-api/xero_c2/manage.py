from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

C2_ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    config = Config(str(C2_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(C2_ROOT / "alembic"))
    config.set_main_option("version_table", "c2_alembic_version")
    return config


def migrate() -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Xero C2 database state.")
    parser.add_argument("command", choices=("migrate",))
    parser.parse_args()
    return migrate()


if __name__ == "__main__":
    raise SystemExit(main())
