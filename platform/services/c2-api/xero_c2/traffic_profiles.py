from __future__ import annotations

import re
import uuid
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Beacon, TrafficProfile, TrafficProfileVersion

TRAFFIC_PROFILE_DEFAULT_TEMPLATE = "default"
TRAFFIC_PROFILE_TEMPLATE_CLOUDFRONT = "cloudfront"
TRAFFIC_PROFILE_TEMPLATE_GOOGLE_ANALYTICS = "google-analytics"

DEFAULT_PROFILE_PATHS = {
    "frame": "/api/v1/beacons/{beacon_id}/frame",
    "poll": "/api/v1/beacons/{beacon_id}/poll",
    "register": "/api/v1/beacons/register",
    "websocket": "/ws/beacon",
}
RESERVED_HEADERS = {
    "authorization",
    "connection",
    "content-length",
    "content-type",
    "host",
    "sec-websocket-key",
    "sec-websocket-protocol",
    "sec-websocket-version",
    "upgrade",
}
HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")


def _template_config(*, sleep_seconds: int, jitter: float, user_agent: str, headers: dict, paths: dict, padding: dict):
    return {
        "headers": headers,
        "jitter": jitter,
        "padding": padding,
        "paths": paths,
        "sleep_seconds": sleep_seconds,
        "user_agent": user_agent,
    }


PROFILE_TEMPLATES = {
    TRAFFIC_PROFILE_TEMPLATE_CLOUDFRONT: {
        "description": "CloudFront-like lab profile with CDN-style paths and headers.",
        "name": "CloudFront CDN",
        "template": TRAFFIC_PROFILE_TEMPLATE_CLOUDFRONT,
        "config": _template_config(
            sleep_seconds=30,
            jitter=0.25,
            user_agent="Amazon CloudFront",
            headers={
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "X-Amz-Cf-Id": "xero-lab-edge",
            },
            paths={
                "frame": "/cdn-cgi/xero/{beacon_id}/frame",
                "poll": "/cdn-cgi/xero/{beacon_id}/collect",
                "register": "/cdn-cgi/xero/register",
                "websocket": "/cdn-cgi/xero/ws",
            },
            padding={"enabled": True, "max_bytes": 96, "min_bytes": 16},
        ),
    },
    TRAFFIC_PROFILE_TEMPLATE_GOOGLE_ANALYTICS: {
        "description": "Google Analytics-like lab profile with collection paths and browser headers.",
        "name": "Google Analytics",
        "template": TRAFFIC_PROFILE_TEMPLATE_GOOGLE_ANALYTICS,
        "config": _template_config(
            sleep_seconds=45,
            jitter=0.2,
            user_agent="Mozilla/5.0 AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            headers={
                "Accept": "image/avif,image/webp,*/*",
                "Referer": "https://www.google-analytics.com/",
                "X-Client-Data": "xero-lab-ga",
            },
            paths={
                "frame": "/g/collect/{beacon_id}/frame",
                "poll": "/g/collect/{beacon_id}",
                "register": "/g/collect/register",
                "websocket": "/g/collect/ws",
            },
            padding={"enabled": True, "max_bytes": 64, "min_bytes": 8},
        ),
    },
}


def default_profile_config(settings) -> dict[str, Any]:
    return normalize_profile_config(
        {
            "headers": {},
            "jitter": settings.beacon_default_jitter,
            "padding": {"enabled": False, "max_bytes": 0, "min_bytes": 0},
            "paths": DEFAULT_PROFILE_PATHS,
            "sleep_seconds": settings.beacon_default_sleep_seconds,
            "user_agent": "xero-go-beacon/0.1",
        }
    )


def normalize_profile_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Traffic profile config must be an object")
    sleep_seconds = _int_range(value.get("sleep_seconds", 30), "sleep_seconds", minimum=1, maximum=86400)
    jitter = _float_range(value.get("jitter", 0.1), "jitter", minimum=0, maximum=1)
    user_agent = _clean_text(value.get("user_agent", "xero-go-beacon/0.1"), "user_agent", max_length=255)
    headers = _normalize_headers(value.get("headers") or {})
    paths = _normalize_paths(value.get("paths") or {})
    padding = _normalize_padding(value.get("padding") or {})
    return {
        "headers": headers,
        "jitter": jitter,
        "padding": padding,
        "paths": paths,
        "sleep_seconds": sleep_seconds,
        "user_agent": user_agent,
    }


def _int_range(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return parsed


def _float_range(value: Any, field: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field} must be between {minimum:g} and {maximum:g}")
    return parsed


def _clean_text(value: Any, field: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be blank")
    if "\r" in normalized or "\n" in normalized or len(normalized) > max_length:
        raise ValueError(f"{field} is invalid")
    return normalized


def _normalize_headers(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("headers must be an object")
    headers: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str) or not HEADER_NAME_PATTERN.fullmatch(raw_name):
            raise ValueError("headers contain an invalid name")
        name = raw_name.strip()
        if name.lower() in RESERVED_HEADERS:
            raise ValueError(f"{name} is a reserved header")
        if not isinstance(raw_value, str):
            raise ValueError("header values must be strings")
        header_value = raw_value.strip()
        if "\r" in header_value or "\n" in header_value or len(header_value) > 512:
            raise ValueError("headers contain an invalid value")
        headers[name] = header_value
    return headers


def _normalize_paths(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("paths must be an object")
    paths = dict(DEFAULT_PROFILE_PATHS)
    for key in ("frame", "poll", "register", "websocket"):
        if key in value:
            paths[key] = _normalize_path(value[key], key)
    return paths


def _normalize_path(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} path must be a string")
    path = value.strip()
    if not path.startswith("/") or "\r" in path or "\n" in path or "://" in path or len(path) > 255:
        raise ValueError(f"{field} path is invalid")
    return path


def _normalize_padding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("padding must be an object")
    enabled = bool(value.get("enabled", False))
    min_bytes = _int_range(value.get("min_bytes", 0), "padding.min_bytes", minimum=0, maximum=4096)
    max_bytes = _int_range(value.get("max_bytes", 0), "padding.max_bytes", minimum=0, maximum=4096)
    if max_bytes < min_bytes:
        raise ValueError("padding.max_bytes must be greater than or equal to padding.min_bytes")
    if not enabled:
        min_bytes = 0
        max_bytes = 0
    return {"enabled": enabled, "max_bytes": max_bytes, "min_bytes": min_bytes}


def ensure_template_profiles(session: Session) -> list[TrafficProfile]:
    profiles: list[TrafficProfile] = []
    for template in PROFILE_TEMPLATES.values():
        profile = session.execute(
            select(TrafficProfile).where(
                TrafficProfile.template == template["template"],
                TrafficProfile.is_template.is_(True),
            )
        ).scalar_one_or_none()
        if profile is None:
            profile = TrafficProfile(
                current_version=1,
                description=template["description"],
                is_template=True,
                name=template["name"],
                template=template["template"],
            )
            session.add(profile)
            session.flush()
            session.add(
                TrafficProfileVersion(
                    config=normalize_profile_config(template["config"]),
                    created_by="system",
                    profile_id=profile.id,
                    version=1,
                )
            )
        profiles.append(profile)
    return profiles


def current_profile_version(session: Session, profile: TrafficProfile) -> TrafficProfileVersion:
    version = session.execute(
        select(TrafficProfileVersion).where(
            TrafficProfileVersion.profile_id == profile.id,
            TrafficProfileVersion.version == profile.current_version,
        )
    ).scalar_one()
    return version


def profile_version(session: Session, profile: TrafficProfile, version: int) -> TrafficProfileVersion | None:
    return session.execute(
        select(TrafficProfileVersion).where(
            TrafficProfileVersion.profile_id == profile.id,
            TrafficProfileVersion.version == version,
        )
    ).scalar_one_or_none()


def public_traffic_profile(session: Session, profile: TrafficProfile, *, include_config: bool = True) -> dict[str, Any]:
    current = current_profile_version(session, profile)
    payload: dict[str, Any] = {
        "created_at": profile.created_at.isoformat(),
        "current_version": profile.current_version,
        "description": profile.description,
        "id": str(profile.id),
        "is_archived": profile.is_archived,
        "is_template": profile.is_template,
        "name": profile.name,
        "template": profile.template,
        "updated_at": profile.updated_at.isoformat(),
    }
    if include_config:
        payload["config"] = deepcopy(current.config)
    return payload


def public_traffic_profile_version(version: TrafficProfileVersion) -> dict[str, Any]:
    return {
        "config": deepcopy(version.config),
        "created_at": version.created_at.isoformat(),
        "created_by": version.created_by,
        "id": str(version.id),
        "profile_id": str(version.profile_id),
        "version": version.version,
    }


def create_profile(
    session: Session,
    *,
    actor_subject: str,
    config: dict[str, Any],
    description: str | None,
    name: str,
    template: str = "custom",
    is_template: bool = False,
) -> TrafficProfile:
    profile = TrafficProfile(
        current_version=1,
        description=_optional_text(description, max_length=512),
        is_template=is_template,
        name=_clean_text(name, "name", max_length=128),
        template=_clean_text(template, "template", max_length=64),
    )
    session.add(profile)
    session.flush()
    session.add(
        TrafficProfileVersion(
            config=normalize_profile_config(config),
            created_by=actor_subject,
            profile_id=profile.id,
            version=1,
        )
    )
    return profile


def update_profile(
    session: Session,
    profile: TrafficProfile,
    *,
    actor_subject: str,
    config: dict[str, Any],
    description: str | None,
    name: str,
) -> TrafficProfile:
    if profile.is_archived:
        raise ValueError("Traffic profile is archived")
    profile.name = _clean_text(name, "name", max_length=128)
    profile.description = _optional_text(description, max_length=512)
    profile.current_version += 1
    session.add(profile)
    session.flush()
    session.add(
        TrafficProfileVersion(
            config=normalize_profile_config(config),
            created_by=actor_subject,
            profile_id=profile.id,
            version=profile.current_version,
        )
    )
    sync_assigned_beacon_timing(session, profile)
    return profile


def clone_profile(
    session: Session,
    source: TrafficProfile,
    *,
    actor_subject: str,
    name: str | None = None,
) -> TrafficProfile:
    source_version = current_profile_version(session, source)
    clone_name = name or f"{source.name} copy"
    return create_profile(
        session,
        actor_subject=actor_subject,
        config=deepcopy(source_version.config),
        description=source.description,
        name=clone_name,
        template=source.template,
        is_template=False,
    )


def rollback_profile(
    session: Session,
    profile: TrafficProfile,
    *,
    actor_subject: str,
    version: int,
) -> TrafficProfile:
    target = profile_version(session, profile, version)
    if target is None:
        raise ValueError("Traffic profile version not found")
    profile.current_version += 1
    session.add(profile)
    session.flush()
    session.add(
        TrafficProfileVersion(
            config=deepcopy(target.config),
            created_by=actor_subject,
            profile_id=profile.id,
            version=profile.current_version,
        )
    )
    sync_assigned_beacon_timing(session, profile)
    return profile


def assign_profile_to_beacon(session: Session, beacon: Beacon, profile: TrafficProfile | None) -> Beacon:
    if profile is not None and profile.is_archived:
        raise ValueError("Traffic profile is archived")
    beacon.profile_id = profile.id if profile is not None else None
    beacon.applied_profile_version = None
    beacon.profile_applied_at = None
    if profile is not None:
        config = current_profile_version(session, profile).config
        beacon.sleep_seconds = int(config["sleep_seconds"])
        beacon.jitter = float(config["jitter"])
    session.add(beacon)
    return beacon


def sync_assigned_beacon_timing(session: Session, profile: TrafficProfile) -> None:
    config = current_profile_version(session, profile).config
    beacons = session.execute(select(Beacon).where(Beacon.profile_id == profile.id)).scalars()
    for beacon in beacons:
        beacon.sleep_seconds = int(config["sleep_seconds"])
        beacon.jitter = float(config["jitter"])
        session.add(beacon)


def effective_profile_payload(session: Session, settings, beacon: Beacon) -> dict[str, Any]:
    if beacon.profile_id is None:
        config = default_profile_config(settings)
        return {
            "config": config,
            "current_version": 0,
            "id": None,
            "is_template": False,
            "name": "Default bootstrap",
            "template": TRAFFIC_PROFILE_DEFAULT_TEMPLATE,
        }
    profile = session.get(TrafficProfile, beacon.profile_id)
    if profile is None or profile.is_archived:
        config = default_profile_config(settings)
        return {
            "config": config,
            "current_version": 0,
            "id": None,
            "is_template": False,
            "name": "Default bootstrap",
            "template": TRAFFIC_PROFILE_DEFAULT_TEMPLATE,
        }
    current = current_profile_version(session, profile)
    return {
        "config": deepcopy(current.config),
        "current_version": profile.current_version,
        "id": str(profile.id),
        "is_template": profile.is_template,
        "name": profile.name,
        "template": profile.template,
    }


def apply_profile_ack(session: Session, settings, beacon: Beacon) -> dict[str, Any]:
    profile_payload = effective_profile_payload(session, settings, beacon)
    config = profile_payload["config"]
    beacon.sleep_seconds = int(config["sleep_seconds"])
    beacon.jitter = float(config["jitter"])
    if profile_payload["id"] is not None:
        beacon.applied_profile_version = int(profile_payload["current_version"])
        beacon.profile_applied_at = utc_now()
    session.add(beacon)
    return profile_payload


def profile_ack_fields(session: Session, settings, beacon: Beacon) -> dict[str, Any]:
    profile = apply_profile_ack(session, settings, beacon)
    config = profile["config"]
    return {
        "jitter": config["jitter"],
        "profile": profile,
        "sleep": config["sleep_seconds"],
    }


def find_profile(session: Session, profile_id: Any) -> TrafficProfile | None:
    try:
        parsed = uuid.UUID(str(profile_id))
    except (TypeError, ValueError):
        return None
    return session.get(TrafficProfile, parsed)


def _optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if "\r" in normalized or "\n" in normalized or len(normalized) > max_length:
        raise ValueError("Text value is invalid")
    return normalized
