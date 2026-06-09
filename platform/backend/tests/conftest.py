from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from app.config import get_settings
from app.database import clear_database_caches
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_backend_state() -> Generator[None, None, None]:
    get_settings.cache_clear()
    clear_database_caches()
    yield
    get_settings.cache_clear()
    clear_database_caches()


@pytest.fixture
def make_test_client(monkeypatch) -> Generator[Callable[..., TestClient], None, None]:
    clients: list[TestClient] = []

    def factory(*, raise_server_exceptions: bool = True, **env: str) -> TestClient:
        monkeypatch.setenv("APP_ENV", "test")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        clear_database_caches()
        client = TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)
        clients.append(client)
        return client

    yield factory

    for client in clients:
        client.close()
