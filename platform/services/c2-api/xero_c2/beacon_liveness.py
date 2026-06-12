from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.database import session_scope
from xero_common.models import utc_now
from xero_common.redis_bus import get_redis_client, publish_operator_event

from xero_c2.config import Settings
from xero_c2.models import Beacon, BeaconEvent

BEACON_STATUS_ONLINE = "online"
BEACON_STATUS_OFFLINE = "offline"
BEACON_EVENT_REASON_HEARTBEAT = "heartbeat"
BEACON_EVENT_REASON_STALE = "stale-threshold"


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def stale_threshold_seconds(beacon: Beacon, settings: Settings) -> float:
    if settings.beacon_stale_threshold_seconds is not None:
        return float(settings.beacon_stale_threshold_seconds)
    return float(beacon.sleep_seconds) * settings.beacon_stale_threshold_multiplier


def beacon_is_stale(beacon: Beacon, settings: Settings, *, now: datetime | None = None) -> bool:
    checked_at = now or utc_now()
    elapsed = aware_utc(checked_at) - aware_utc(beacon.last_seen)
    return elapsed > timedelta(seconds=stale_threshold_seconds(beacon, settings))


def record_status_transition(
    session: Session,
    beacon: Beacon,
    *,
    old_status: str,
    new_status: str,
    reason: str,
    occurred_at: datetime | None = None,
) -> BeaconEvent | None:
    if old_status == new_status:
        return None
    event = BeaconEvent(
        beacon_id=beacon.id,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        occurred_at=occurred_at or utc_now(),
    )
    session.add(event)
    return event


def apply_runtime_metadata(beacon: Beacon, payload: Any) -> None:
    fields_set = getattr(payload, "model_fields_set", set())
    for field_name in ("hostname", "os", "architecture", "internal_ip", "external_ip", "pid"):
        if field_name in fields_set:
            setattr(beacon, field_name, getattr(payload, field_name))


def mark_stale_beacons_offline(
    session: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[Beacon]:
    checked_at = now or utc_now()
    stale_beacons: list[Beacon] = []
    beacons = session.execute(
        select(Beacon).where(Beacon.status != BEACON_STATUS_OFFLINE).order_by(Beacon.last_seen.asc())
    ).scalars()
    for beacon in beacons:
        if not beacon_is_stale(beacon, settings, now=checked_at):
            continue
        old_status = beacon.status
        beacon.status = BEACON_STATUS_OFFLINE
        record_status_transition(
            session,
            beacon,
            old_status=old_status,
            new_status=BEACON_STATUS_OFFLINE,
            reason=BEACON_EVENT_REASON_STALE,
            occurred_at=checked_at,
        )
        stale_beacons.append(beacon)
    return stale_beacons


async def publish_beacon_event(app: Any, settings: Settings, event_type: str, beacon_payload: dict) -> None:
    redis_client = get_redis_client_from_app(app)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"beacon": beacon_payload},
        scope={"beacon_id": beacon_payload["id"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


def get_redis_client_from_app(app: Any):
    request_like = type("RequestLike", (), {"app": app})()
    return get_redis_client(request_like)


async def run_beacon_stale_monitor(app: Any, settings: Settings, public_beacon) -> None:
    while True:
        await asyncio.sleep(settings.beacon_heartbeat_check_interval_seconds)
        try:
            stale_payloads: list[dict] = []
            with session_scope(settings) as session:
                stale_beacons = mark_stale_beacons_offline(session, settings)
                session.flush()
                stale_payloads = [public_beacon(beacon) for beacon in stale_beacons]
            for beacon_payload in stale_payloads:
                await publish_beacon_event(app, settings, "beacon.status.changed", beacon_payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            continue
