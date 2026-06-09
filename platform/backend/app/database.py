from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings


def sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def engine_kwargs_for_url(normalized_url: str, settings: Settings) -> dict:
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
    settings = get_settings().model_copy(
        update={
            key: value
            for key, value in {
                "database_pool_size": pool_size,
                "database_max_overflow": max_overflow,
                "database_pool_timeout_seconds": pool_timeout_seconds,
                "database_pool_recycle_seconds": pool_recycle_seconds,
            }.items()
            if value is not None
        }
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


def session_factory_for_settings(settings: Settings) -> sessionmaker[Session]:
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


def get_db_session() -> Generator[Session, None, None]:
    settings = get_settings()
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        yield session


@contextmanager
def session_scope(settings: Settings | None = None) -> Generator[Session, None, None]:
    active_settings = settings or get_settings()
    SessionFactory = session_factory_for_settings(active_settings)
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
