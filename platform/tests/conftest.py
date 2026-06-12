from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from xero_bff.config import get_settings as get_bff_settings
from xero_bff.main import create_app as create_bff_app
from xero_c2.config import get_settings as get_c2_settings
from xero_c2.main import create_app as create_c2_app
from xero_common.database import clear_database_caches


@pytest.fixture(autouse=True)
def reset_service_state() -> Generator[None, None, None]:
    get_bff_settings.cache_clear()
    get_c2_settings.cache_clear()
    clear_database_caches()
    yield
    get_bff_settings.cache_clear()
    get_c2_settings.cache_clear()
    clear_database_caches()


@pytest.fixture
def make_bff_client(monkeypatch) -> Generator[Callable[..., TestClient], None, None]:
    clients: list[TestClient] = []

    def factory(*, raise_server_exceptions: bool = True, **env: str) -> TestClient:
        monkeypatch.setenv("APP_ENV", "test")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_bff_settings.cache_clear()
        clear_database_caches()
        client = TestClient(create_bff_app(), raise_server_exceptions=raise_server_exceptions)
        clients.append(client)
        return client

    yield factory

    for client in clients:
        client.close()


@pytest.fixture
def make_c2_client(monkeypatch) -> Generator[Callable[..., TestClient], None, None]:
    clients: list[TestClient] = []

    def factory(*, raise_server_exceptions: bool = True, **env: str) -> TestClient:
        monkeypatch.setenv("APP_ENV", "test")
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_c2_settings.cache_clear()
        clear_database_caches()
        client = TestClient(create_c2_app(), raise_server_exceptions=raise_server_exceptions)
        clients.append(client)
        return client

    yield factory

    for client in clients:
        client.close()
