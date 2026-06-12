from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from xero_common.worker_client import (
    WorkerClientError,
    heartbeat_worker,
    load_worker_session,
    register_worker,
    save_worker_session,
)

from xero_scanner.config import Settings, get_settings

CAPABILITIES = ["embedded-compatible", "tcp-connect", "service-enumeration"]
WORKER_KIND = "scanner"


def liveness_payload() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "role": settings.service_role,
        "environment": settings.app_env,
    }


async def worker_pairing_loop(app: FastAPI, settings: Settings) -> None:
    session = load_worker_session(settings.worker_token_file)
    if session is None and settings.worker_pairing_token:
        try:
            session = await asyncio.to_thread(
                register_worker,
                base_url=settings.c2_base_url,
                kind=WORKER_KIND,
                name=settings.worker_name or settings.service_name,
                pairing_token=settings.worker_pairing_token,
                endpoint=settings.worker_endpoint,
                capabilities=CAPABILITIES,
                capacity=settings.worker_capacity,
                current_load=0,
                version=settings.worker_version,
            )
            await asyncio.to_thread(save_worker_session, settings.worker_token_file, session)
            app.state.worker_status = "registered"
        except WorkerClientError as exc:
            app.state.worker_status = "registration_failed"
            app.state.worker_error = str(exc)
            session = None

    while True:
        if session is not None:
            try:
                await asyncio.to_thread(
                    heartbeat_worker,
                    base_url=settings.c2_base_url,
                    session=session,
                    endpoint=settings.worker_endpoint,
                    capabilities=CAPABILITIES,
                    capacity=settings.worker_capacity,
                    current_load=0,
                    version=settings.worker_version,
                )
                app.state.worker_status = "online"
                app.state.worker_error = ""
            except WorkerClientError as exc:
                app.state.worker_status = "heartbeat_failed"
                app.state.worker_error = str(exc)
        sleep_seconds = session.heartbeat_interval_seconds if session else settings.worker_heartbeat_interval_seconds
        await asyncio.sleep(sleep_seconds)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.worker_status = "standalone"
        app.state.worker_error = ""
        task: asyncio.Task[None] | None = None
        if settings.c2_base_url:
            task = asyncio.create_task(worker_pairing_loop(app, settings))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Xero Scanner API", version="0.1.0", lifespan=lifespan)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return liveness_payload()

    @app.get("/ready", tags=["health"])
    def ready() -> dict[str, str]:
        return {
            **liveness_payload(),
            "status": "ready",
            "worker_status": getattr(app.state, "worker_status", "standalone"),
        }

    return app


app = create_app()
