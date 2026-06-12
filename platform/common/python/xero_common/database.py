from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from typing import Protocol

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseSettings(Protocol):
    database_url: str
    database_pool_size: int
    database_max_overflow: int
    database_pool_timeout_seconds: int
    database_pool_recycle_seconds: int


def sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def engine_kwargs_for_url(normalized_url: str, settings: DatabaseSettings) -> dict:
    engine_kwargs: dict = {
        "future": True,
        "pool_pre_ping": True,
    }
    if normalized_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        return engine_kwargs

    engine_kwargs.update(
        {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout_seconds,
            "pool_recycle": settings.database_pool_recycle_seconds,
        }
    )
    return engine_kwargs


@lru_cache
def get_engine(
    database_url: str,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout_seconds: int | None = None,
    pool_recycle_seconds: int | None = None,
) -> Engine:
    settings = RuntimeDatabaseSettings(
        database_url=database_url,
        database_pool_size=pool_size or 5,
        database_max_overflow=10 if max_overflow is None else max_overflow,
        database_pool_timeout_seconds=pool_timeout_seconds or 30,
        database_pool_recycle_seconds=1800 if pool_recycle_seconds is None else pool_recycle_seconds,
    )
    normalized_url = sqlalchemy_database_url(database_url)
    return create_engine(normalized_url, **engine_kwargs_for_url(normalized_url, settings))


@lru_cache
def get_session_factory(
    database_url: str,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout_seconds: int | None = None,
    pool_recycle_seconds: int | None = None,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(
            database_url,
            pool_size,
            max_overflow,
            pool_timeout_seconds,
            pool_recycle_seconds,
        ),
        expire_on_commit=False,
    )


def session_factory_for_settings(settings: DatabaseSettings) -> sessionmaker[Session]:
    return get_session_factory(
        settings.database_url,
        settings.database_pool_size,
        settings.database_max_overflow,
        settings.database_pool_timeout_seconds,
        settings.database_pool_recycle_seconds,
    )


def clear_database_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@contextmanager
def session_scope(settings: DatabaseSettings) -> Generator[Session, None, None]:
    SessionFactory = session_factory_for_settings(settings)
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class RuntimeDatabaseSettings:
    def __init__(
        self,
        *,
        database_url: str,
        database_pool_size: int,
        database_max_overflow: int,
        database_pool_timeout_seconds: int,
        database_pool_recycle_seconds: int,
    ) -> None:
        self.database_url = database_url
        self.database_pool_size = database_pool_size
        self.database_max_overflow = database_max_overflow
        self.database_pool_timeout_seconds = database_pool_timeout_seconds
        self.database_pool_recycle_seconds = database_pool_recycle_seconds
