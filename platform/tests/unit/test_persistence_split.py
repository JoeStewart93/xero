from __future__ import annotations

from alembic import command
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, select
from xero_bff.config import Settings as BffSettings
from xero_bff.config import get_settings as get_bff_settings
from xero_bff.manage import alembic_config as bff_alembic_config
from xero_bff.models import Base as BffBase
from xero_bff.models import User
from xero_c2.config import Settings as C2Settings
from xero_c2.config import get_settings as get_c2_settings
from xero_c2.manage import alembic_config as c2_alembic_config
from xero_c2.models import Base as C2Base
from xero_c2.models import Beacon
from xero_common import crud
from xero_common.database import (
    clear_database_caches,
    engine_kwargs_for_url,
    get_engine,
    get_session_factory,
    session_scope,
    sqlalchemy_database_url,
)


def test_common_engine_pool_options_preserve_sqlite_compatibility():
    postgres_settings = BffSettings(
        app_env="test",
        database_url="postgresql://user:pass@postgres:5432/db",
        database_pool_size=8,
        database_max_overflow=2,
        database_pool_timeout_seconds=9,
        database_pool_recycle_seconds=600,
    )
    postgres_kwargs = engine_kwargs_for_url(sqlalchemy_database_url(postgres_settings.database_url), postgres_settings)
    sqlite_settings = BffSettings(app_env="test", database_url="sqlite+pysqlite:///test.db")
    sqlite_kwargs = engine_kwargs_for_url(sqlalchemy_database_url(sqlite_settings.database_url), sqlite_settings)

    assert postgres_kwargs["pool_size"] == 8
    assert postgres_kwargs["max_overflow"] == 2
    assert postgres_kwargs["pool_timeout"] == 9
    assert postgres_kwargs["pool_recycle"] == 600
    assert sqlite_kwargs["connect_args"] == {"check_same_thread": False}
    assert "pool_size" not in sqlite_kwargs


def test_session_scope_commits_and_rolls_back(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'sessions.db'}"
    settings = BffSettings(app_env="test", database_url=database_url)
    BffBase.metadata.create_all(bind=get_engine(database_url))

    with session_scope(settings) as session:
        session.add(User(username="committed", password_hash="hash", role="operator", is_enabled=True))

    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        assert session.execute(select(User).where(User.username == "committed")).scalar_one_or_none() is not None

    try:
        with session_scope(settings) as session:
            session.add(User(username="rolled-back", password_hash="hash", role="operator", is_enabled=True))
            raise RuntimeError("rollback")
    except RuntimeError:
        pass

    with SessionFactory() as session:
        assert session.execute(select(User).where(User.username == "rolled-back")).scalar_one_or_none() is None


def test_bff_migrations_create_only_user_schema(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'bff-migrations.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_bff_settings.cache_clear()
    clear_database_caches()

    command.upgrade(bff_alembic_config(), "head")

    engine = get_engine(database_url)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names()
    assert "beacons" not in inspector.get_table_names()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"version_table": "bff_alembic_version"})
        assert context.get_current_heads() == ("bff_0002_role_enabled",)


def test_c2_migrations_create_only_beacon_schema(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'c2-migrations.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    get_c2_settings.cache_clear()
    clear_database_caches()

    command.upgrade(c2_alembic_config(), "head")

    engine = get_engine(database_url)
    inspector = inspect(engine)
    assert "users" not in inspector.get_table_names()
    assert "beacons" in inspector.get_table_names()
    assert "beacon_events" in inspector.get_table_names()
    assert "infrastructure_workers" in inspector.get_table_names()
    assert "worker_pairing_tokens" in inspector.get_table_names()
    assert "worker_events" in inspector.get_table_names()
    assert "protocol_security_events" in inspector.get_table_names()
    assert "protocol_frame_receipts" in inspector.get_table_names()
    assert "tasks" in inspector.get_table_names()
    assert "protocol_version" in {column["name"] for column in inspector.get_columns("beacons")}
    assert "protocol_peer_public_key_b64" in {column["name"] for column in inspector.get_columns("beacons")}
    assert "transport_mode" in {column["name"] for column in inspector.get_columns("beacons")}
    assert "transport_connected" in {column["name"] for column in inspector.get_columns("beacons")}
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    assert {"beacon_id", "module", "args", "status", "priority", "dispatched_at", "cancelled_at"}.issubset(
        task_columns
    )
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"version_table": "c2_alembic_version"})
        assert context.get_current_heads() == ("c2_0007_task_queue",)


def test_generic_crud_helpers_work_with_service_models(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'crud.db'}"
    settings = C2Settings(app_env="test", database_url=database_url)
    C2Base.metadata.create_all(bind=get_engine(database_url))

    with session_scope(settings) as session:
        beacon = crud.create(
            session,
            Beacon(
                machine_fingerprint_hash="crud-fingerprint",
                hostname="crud-host",
                os="Windows",
                architecture="x64",
                internal_ip="10.0.0.5",
                external_ip=None,
                pid=100,
                status="online",
                beacon_token_hash="sha256:hash",
            ),
        )
        beacon_id = beacon.id
        assert crud.read(session, Beacon, beacon_id) is not None
        assert crud.update(session, beacon, hostname="crud-renamed").hostname == "crud-renamed"
        crud.delete(session, beacon)

    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        assert crud.read(session, Beacon, beacon_id) is None
