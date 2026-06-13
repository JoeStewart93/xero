from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import InteractiveSession, RegistryAuditEvent, RegistryConfirmation

REGISTRY_SESSION_TYPE = "registry"

SESSION_OP_REG_LIST_KEY = "reg_list_key"
SESSION_OP_REG_READ_VALUE = "reg_read_value"
SESSION_OP_REG_PREPARE_WRITE_VALUE = "reg_prepare_write_value"
SESSION_OP_REG_WRITE_VALUE = "reg_write_value"
SESSION_OP_REG_PREPARE_DELETE_VALUE = "reg_prepare_delete_value"
SESSION_OP_REG_DELETE_VALUE = "reg_delete_value"
SESSION_OP_REG_CONFIRM_TOKEN = "reg_confirm_token"

REGISTRY_SESSION_OPS = {
    SESSION_OP_REG_LIST_KEY,
    SESSION_OP_REG_READ_VALUE,
    SESSION_OP_REG_PREPARE_WRITE_VALUE,
    SESSION_OP_REG_WRITE_VALUE,
    SESSION_OP_REG_PREPARE_DELETE_VALUE,
    SESSION_OP_REG_DELETE_VALUE,
}
REGISTRY_BEACON_OPS = {
    SESSION_OP_REG_LIST_KEY,
    SESSION_OP_REG_READ_VALUE,
    SESSION_OP_REG_WRITE_VALUE,
    SESSION_OP_REG_DELETE_VALUE,
}
REGISTRY_WRITABLE_TYPES = {"REG_DWORD", "REG_SZ"}
REGISTRY_ERROR_CODES = {
    "access_denied",
    "confirm_token_invalid",
    "hive_invalid",
    "key_invalid",
    "not_found",
    "type_unsupported",
    "unsupported_operation",
    "value_invalid",
}

HIVE_ALIASES = {
    "HKCR": "HKCR",
    "HKEY_CLASSES_ROOT": "HKCR",
    "HKCU": "HKCU",
    "HKEY_CURRENT_USER": "HKCU",
    "HKLM": "HKLM",
    "HKEY_LOCAL_MACHINE": "HKLM",
    "HKU": "HKU",
    "HKEY_USERS": "HKU",
    "HKCC": "HKCC",
    "HKEY_CURRENT_CONFIG": "HKCC",
}


def normalize_registry_hive(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Registry hive is required")
    hive = value.strip().upper()
    normalized = HIVE_ALIASES.get(hive)
    if normalized is None:
        raise ValueError("Registry hive is invalid")
    return normalized


def normalize_registry_key_path(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Registry key_path must be a string")
    key_path = value.replace("/", "\\").strip().strip("\\")
    if "\x00" in key_path:
        raise ValueError("Registry key_path is invalid")
    parts = [part.strip() for part in key_path.split("\\") if part.strip()]
    if any(part in {".", ".."} for part in parts):
        raise ValueError("Registry key_path cannot traverse")
    normalized = "\\".join(parts)
    if len(normalized) > 512:
        raise ValueError("Registry key_path is too long")
    return normalized


def normalize_registry_value_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Registry value_name is required")
    name = value.strip()
    if "\x00" in name or len(name) > 255:
        raise ValueError("Registry value_name is invalid")
    return name


def normalize_registry_value_type(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Registry value_type is required")
    value_type = value.strip().upper()
    if value_type not in REGISTRY_WRITABLE_TYPES:
        raise ValueError("Registry value_type is read-only or unsupported")
    return value_type


def normalize_registry_value(value_type: str, value: Any) -> str | int:
    if value_type == "REG_SZ":
        if not isinstance(value, str):
            raise ValueError("REG_SZ value must be a string")
        if "\x00" in value:
            raise ValueError("REG_SZ value is invalid")
        return value
    if value_type == "REG_DWORD":
        if isinstance(value, bool):
            raise ValueError("REG_DWORD value must be an integer")
        if isinstance(value, str):
            value = value.strip()
            if value.lower().startswith("0x"):
                parsed = int(value, 16)
            else:
                parsed = int(value, 10)
        elif isinstance(value, int):
            parsed = value
        else:
            raise ValueError("REG_DWORD value must be an integer")
        if parsed < 0 or parsed > 0xFFFFFFFF:
            raise ValueError("REG_DWORD value is out of range")
        return parsed
    raise ValueError("Registry value_type is read-only or unsupported")


def registry_value_digest(value_type: str | None, value: Any) -> str | None:
    if value_type is None:
        return None
    normalized = {"value": value, "value_type": value_type}
    raw = json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def registry_value_length(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, int):
        return 4
    return len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def hash_confirm_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_registry_request(raw_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("Registry message must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Registry message must be a JSON object")
    op = payload.get("op")
    if op == "ping":
        return {"op": "ping"}
    if op == "close":
        return {"op": "close"}
    if op not in REGISTRY_SESSION_OPS:
        raise ValueError("Registry message op is invalid")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("Registry request_id is required")
    message: dict[str, Any] = {
        "hive": normalize_registry_hive(payload.get("hive")),
        "key_path": normalize_registry_key_path(payload.get("key_path")),
        "op": op,
        "request_id": request_id.strip(),
    }
    if op in {
        SESSION_OP_REG_READ_VALUE,
        SESSION_OP_REG_PREPARE_WRITE_VALUE,
        SESSION_OP_REG_WRITE_VALUE,
        SESSION_OP_REG_PREPARE_DELETE_VALUE,
        SESSION_OP_REG_DELETE_VALUE,
    }:
        message["value_name"] = normalize_registry_value_name(payload.get("value_name"))
    if op in {SESSION_OP_REG_PREPARE_WRITE_VALUE, SESSION_OP_REG_WRITE_VALUE}:
        value_type = normalize_registry_value_type(payload.get("value_type"))
        value = normalize_registry_value(value_type, payload.get("value"))
        message["value_type"] = value_type
        message["value"] = value
        message["value_digest"] = registry_value_digest(value_type, value)
        message["value_length"] = registry_value_length(value)
    if op in {SESSION_OP_REG_WRITE_VALUE, SESSION_OP_REG_DELETE_VALUE}:
        token = payload.get("confirm_token")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Registry confirm_token is required")
        message["confirm_token"] = token.strip()
    return message


def create_registry_confirmation(
    session: Session,
    *,
    actor_subject: str,
    ttl_seconds: int,
    registry_session: InteractiveSession,
    request: dict[str, Any],
) -> dict[str, Any]:
    operation = _confirmation_operation(request["op"])
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(seconds=ttl_seconds)
    confirmation = RegistryConfirmation(
        actor_subject=actor_subject,
        beacon_id=registry_session.beacon_id,
        expires_at=expires_at,
        hive=request["hive"],
        key_path=request["key_path"],
        operation=operation,
        session_id=registry_session.id,
        token_hash=hash_confirm_token(token),
        value_digest=request.get("value_digest"),
        value_length=request.get("value_length"),
        value_name=request.get("value_name", ""),
        value_type=request.get("value_type"),
    )
    session.add(confirmation)
    return {
        "action": operation,
        "confirm_token": token,
        "expires_at": expires_at.isoformat(),
        "hive": confirmation.hive,
        "key_path": confirmation.key_path,
        "ok": True,
        "op": SESSION_OP_REG_CONFIRM_TOKEN,
        "request_id": request["request_id"],
        "session_id": str(registry_session.id),
        "value_name": confirmation.value_name,
        "value_type": confirmation.value_type,
    }


def consume_registry_confirmation(
    session: Session,
    *,
    actor_subject: str,
    registry_session: InteractiveSession,
    request: dict[str, Any],
) -> None:
    token_hash = hash_confirm_token(str(request["confirm_token"]))
    confirmation = session.execute(
        select(RegistryConfirmation).where(
            RegistryConfirmation.actor_subject == actor_subject,
            RegistryConfirmation.session_id == registry_session.id,
            RegistryConfirmation.token_hash == token_hash,
        )
    ).scalar_one_or_none()
    if confirmation is None or confirmation.used_at is not None or _is_expired(confirmation.expires_at):
        raise ValueError("Registry confirm_token is invalid or expired")
    if confirmation.operation != _confirmation_operation(request["op"]):
        raise ValueError("Registry confirm_token action does not match request")
    expected = {
        "hive": confirmation.hive,
        "key_path": confirmation.key_path,
        "value_name": confirmation.value_name,
    }
    for field, expected_value in expected.items():
        if request.get(field) != expected_value:
            raise ValueError("Registry confirm_token target does not match request")
    if confirmation.value_type != request.get("value_type"):
        raise ValueError("Registry confirm_token value type does not match request")
    if confirmation.value_digest != request.get("value_digest"):
        raise ValueError("Registry confirm_token value does not match request")
    confirmation.used_at = utc_now()
    session.add(confirmation)


def registry_frame_fields(request: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "hive": request["hive"],
        "key_path": request["key_path"],
        "request_id": request["request_id"],
        "session_type": REGISTRY_SESSION_TYPE,
        "value_name": request.get("value_name"),
        "value_type": request.get("value_type"),
        "value": request.get("value"),
    }
    return {key: value for key, value in fields.items() if value is not None}


def registry_operator_message(payload: dict[str, Any], session_id: uuid.UUID) -> dict[str, Any]:
    message = {
        "error_code": payload.get("error_code"),
        "hive": payload.get("hive"),
        "key_path": normalize_registry_key_path(payload.get("key_path")),
        "message": payload.get("message"),
        "ok": payload.get("ok", True),
        "op": payload.get("op"),
        "request_id": payload.get("request_id"),
        "session_id": str(session_id),
        "subkeys": payload.get("subkeys", []),
        "value": payload.get("value"),
        "value_name": payload.get("value_name"),
        "value_type": payload.get("value_type"),
        "values": payload.get("values", []),
    }
    return {key: value for key, value in message.items() if value is not None}


def record_registry_audit_result(
    session: Session,
    registry_session: InteractiveSession,
    payload: dict[str, Any],
) -> None:
    op = str(payload.get("op") or "")
    if op not in {SESSION_OP_REG_WRITE_VALUE, SESSION_OP_REG_DELETE_VALUE}:
        return
    value_type = payload.get("value_type") if isinstance(payload.get("value_type"), str) else None
    value = payload.get("value")
    value_digest = registry_value_digest(value_type, value) if value_type and op == SESSION_OP_REG_WRITE_VALUE else None
    event = RegistryAuditEvent(
        actor_subject=registry_session.actor_subject,
        beacon_id=registry_session.beacon_id,
        error_code=payload.get("error_code") if isinstance(payload.get("error_code"), str) else None,
        hive=normalize_registry_hive(payload.get("hive")),
        key_path=normalize_registry_key_path(payload.get("key_path")),
        message=str(payload.get("message") or "")[:512] or None,
        operation=op.removeprefix("reg_"),
        result="succeeded" if payload.get("ok", True) is True else "failed",
        session_id=registry_session.id,
        value_digest=value_digest,
        value_length=registry_value_length(value) if op == SESSION_OP_REG_WRITE_VALUE else None,
        value_name=normalize_registry_value_name(payload.get("value_name")),
        value_type=value_type,
    )
    session.add(event)


def _confirmation_operation(op: str) -> str:
    if op in {SESSION_OP_REG_PREPARE_WRITE_VALUE, SESSION_OP_REG_WRITE_VALUE}:
        return SESSION_OP_REG_WRITE_VALUE
    if op in {SESSION_OP_REG_PREPARE_DELETE_VALUE, SESSION_OP_REG_DELETE_VALUE}:
        return SESSION_OP_REG_DELETE_VALUE
    raise ValueError("Registry operation does not require confirmation")


def _is_expired(expires_at) -> bool:
    now = utc_now()
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    return expires_at <= now
