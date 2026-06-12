from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from xero_bff.config import get_settings
from xero_bff.models import Base
from xero_common.database import sqlalchemy_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    get_settings.cache_clear()
    return sqlalchemy_database_url(get_settings().database_url)


def configure_context(connection=None, url: str | None = None) -> None:
    options = {
        "target_metadata": target_metadata,
        "version_table": "bff_alembic_version",
    }
    if connection is not None:
        options["connection"] = connection
    if url is not None:
        options["url"] = url
        options["literal_binds"] = True
        options["dialect_opts"] = {"paramstyle": "named"}
    context.configure(**options)


def run_migrations_offline() -> None:
    configure_context(url=database_url())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        configure_context(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
