from __future__ import annotations

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from app import crud
from app.config import Settings, get_settings
from app.database import (
    clear_database_caches,
    engine_kwargs_for_url,
    get_engine,
    get_session_factory,
    session_scope,
    sqlalchemy_database_url,
)
from app.manage import alembic_config
from app.models import Base, User
from sqlalchemy import inspect, select


def sqlite_settings(monkeypatch, tmp_path, name: str = "persistence.db") -> Settings:
    database_url = f"sqlite+pysqlite:///{tmp_path / name}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    clear_database_caches()
    return get_settings()


def create_schema(settings: Settings) -> None:
    Base.metadata.create_all(bind=get_engine(settings.database_url))


def test_settings_parse_database_pool_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "7")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "13")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "11")
    monkeypatch.setenv("DATABASE_POOL_RECYCLE_SECONDS", "900")
    monkeypatch.setenv("BEACON_HEARTBEAT_CHECK_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("BEACON_STALE_THRESHOLD_MULTIPLIER", "2.5")
    monkeypatch.setenv("BEACON_STALE_THRESHOLD_SECONDS", "75")

    settings = Settings()

    assert settings.database_pool_size == 7
    assert settings.database_max_overflow == 13
    assert settings.database_pool_timeout_seconds == 11
    assert settings.database_pool_recycle_seconds == 900
    assert settings.beacon_heartbeat_check_interval_seconds == 5
    assert settings.beacon_stale_threshold_multiplier == 2.5
    assert settings.beacon_stale_threshold_seconds == 75


def test_engine_kwargs_apply_postgres_pool_settings_and_preserve_sqlite_compatibility():
    postgres_settings = Settings(
        app_env="test",
        database_url="postgresql://user:pass@postgres:5432/db",
        database_pool_size=8,
        database_max_overflow=2,
        database_pool_timeout_seconds=9,
        database_pool_recycle_seconds=600,
    )
    postgres_kwargs = engine_kwargs_for_url(sqlalchemy_database_url(postgres_settings.database_url), postgres_settings)

    assert postgres_kwargs["pool_pre_ping"] is True
    assert postgres_kwargs["pool_size"] == 8
    assert postgres_kwargs["max_overflow"] == 2
    assert postgres_kwargs["pool_timeout"] == 9
    assert postgres_kwargs["pool_recycle"] == 600

    sqlite_settings = Settings(app_env="test", database_url="sqlite+pysqlite:///test.db")
    sqlite_kwargs = engine_kwargs_for_url(sqlalchemy_database_url(sqlite_settings.database_url), sqlite_settings)

    assert sqlite_kwargs["connect_args"] == {"check_same_thread": False}
    assert "pool_size" not in sqlite_kwargs
    assert "max_overflow" not in sqlite_kwargs


def test_session_factory_creates_and_closes_sessions(monkeypatch, tmp_path):
    settings = sqlite_settings(monkeypatch, tmp_path)
    create_schema(settings)

    SessionFactory = get_session_factory(settings.database_url)
    session = SessionFactory()

    assert session.get_bind() is not None
    session.close()
    assert not session.in_transaction()


def test_session_scope_commits_success_and_rolls_back_on_error(monkeypatch, tmp_path):
    settings = sqlite_settings(monkeypatch, tmp_path)
    create_schema(settings)

    with session_scope(settings) as session:
        session.add(User(username="committed", password_hash="hash", role="operator", is_enabled=True))

    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        committed = session.execute(select(User).where(User.username == "committed")).scalar_one_or_none()
    assert committed is not None

    with pytest.raises(RuntimeError):
        with session_scope(settings) as session:
            session.add(User(username="rolled-back", password_hash="hash", role="operator", is_enabled=True))
            raise RuntimeError("rollback")

    with SessionFactory() as session:
        rolled_back = session.execute(select(User).where(User.username == "rolled-back")).scalar_one_or_none()
    assert rolled_back is None


def test_migration_upgrade_head_on_sqlite_test_db(monkeypatch, tmp_path):
    settings = sqlite_settings(monkeypatch, tmp_path, "migrations.db")

    command.upgrade(alembic_config(), "head")
    command.upgrade(alembic_config(), "head")

    engine = get_engine(settings.database_url)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names()
    assert "beacons" in inspector.get_table_names()
    assert {"id", "username", "password_hash", "role", "is_enabled", "created_at", "updated_at"}.issubset(
        {column["name"] for column in inspector.get_columns("users")}
    )
    assert {
        "id",
        "machine_fingerprint_hash",
        "hostname",
        "os",
        "architecture",
        "internal_ip",
        "external_ip",
        "pid",
        "status",
        "sleep_seconds",
        "jitter",
        "beacon_token_hash",
        "beacon_token_issued_at",
        "first_seen",
        "last_seen",
        "created_at",
        "updated_at",
    }.issubset({column["name"] for column in inspector.get_columns("beacons")})
    assert "beacon_events" in inspector.get_table_names()
    assert {
        "id",
        "beacon_id",
        "old_status",
        "new_status",
        "reason",
        "occurred_at",
        "created_at",
        "updated_at",
    }.issubset({column["name"] for column in inspector.get_columns("beacon_events")})

    with engine.connect() as connection:
        current_heads = MigrationContext.configure(connection).get_current_heads()
    assert current_heads == ("0007_beacon_heartbeat_keepalive",)


def test_crud_create_read_update_delete(monkeypatch, tmp_path):
    settings = sqlite_settings(monkeypatch, tmp_path)
    create_schema(settings)

    with session_scope(settings) as session:
        user = crud.create(
            session,
            User(username="crud-user", password_hash="hash", role="operator", is_enabled=True),
        )
        user_id = user.id

        read_user = crud.read(session, User, user_id)
        assert read_user is not None
        assert read_user.username == "crud-user"

        updated_user = crud.update(session, read_user, role="admin", is_enabled=False)
        assert updated_user.role == "admin"
        assert updated_user.is_enabled is False
        assert [item.username for item in crud.list_all(session, User)] == ["crud-user"]

        crud.delete(session, updated_user)

    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        assert crud.read(session, User, user_id) is None
