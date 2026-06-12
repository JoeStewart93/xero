from __future__ import annotations

import asyncio
import threading
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect, WebSocketState
from xero_c2.beacon_liveness import BEACON_STATUS_OFFLINE, mark_stale_beacons_offline
from xero_c2.beacon_transport import WS_CLOSE_DUPLICATE, WS_CLOSE_OVERLOADED, BeaconTransportManager
from xero_c2.config import get_settings
from xero_c2.infrastructure_workers import mark_stale_workers
from xero_c2.models import (
    Base,
    Beacon,
    BeaconEvent,
    InfrastructureWorker,
    ProtocolFrameReceipt,
    ProtocolSecurityEvent,
    WorkerEvent,
)
from xero_c2.protocol import HEARTBEAT, REGISTER, TASK_POLL, TASK_RESULT
from xero_common.database import clear_database_caches, get_engine, get_session_factory
from xero_common.models import utc_now
from xero_common.security import hash_beacon_token

from tests.helpers.protocol_frames import decode_protocol_response, encode_protocol_test_frame


@pytest.fixture
def c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("BEACON_DEFAULT_SLEEP_SECONDS", "5")
    monkeypatch.setenv("BEACON_DEFAULT_JITTER", "0.25")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client()


@pytest.fixture
def protocol_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'protocol-c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_PROTOCOL_FRAME_HARNESS_ENABLED", "true")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client()


@pytest.fixture
def longpoll_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'longpoll-c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_LONGPOLL_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_BEACON_LONGPOLL_TIMEOUT_SECONDS="1",
    )


def connect_c2(client) -> str:
    response = client.post("/api/v1/c2/connect", json={"password": "connect-me"})
    assert response.status_code == 200
    return response.json()["access_token"]


def register_payload(**overrides):
    payload = {
        "machine_fingerprint_hash": f"fingerprint-{uuid.uuid4()}",
        "hostname": "test-host",
        "os": "Windows 11",
        "architecture": "x64",
        "internal_ip": "10.20.0.5",
        "external_ip": "198.51.100.5",
        "pid": 2222,
    }
    payload.update(overrides)
    return payload


def register_beacon(client, **overrides) -> dict:
    response = client.post("/api/v1/beacons/register", json=register_payload(**overrides))
    assert response.status_code == 200
    return response.json()


def test_c2_connect_and_session(c2_client):
    bad = c2_client.post("/api/v1/c2/connect", json={"password": "wrong"})
    token = connect_c2(c2_client)
    session = c2_client.get("/api/v1/c2/session", headers={"Authorization": f"Bearer {token}"})

    assert bad.status_code == 401
    assert session.status_code == 200
    assert session.json()["service_role"] == "c2"


def test_protocol_info_requires_c2_auth_and_exposes_public_metadata(c2_client):
    unauthenticated = c2_client.get("/api/v1/protocol")
    token = connect_c2(c2_client)
    response = c2_client.get("/api/v1/protocol", headers={"Authorization": f"Bearer {token}"})

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_version"] == 1
    assert payload["supported_versions"] == [1]
    assert payload["key_exchange"] == "X25519-HKDF-SHA256"
    assert payload["encryption"] == "AES-256-GCM"
    assert payload["integrity"] == "HMAC-SHA256"
    assert payload["frame_header_length"] == 72
    assert payload["c2_public_key_b64"]
    assert payload["frame_harness_enabled"] is False


def test_protocol_frame_harness_is_disabled_by_default(c2_client):
    token = connect_c2(c2_client)
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    response = c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 403


def test_protocol_register_frame_updates_beacon_metadata_and_returns_ack(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    ack = decode_protocol_response(response.content)
    assert ack["acknowledged_message_type"] == "REGISTER"
    assert ack["selected_protocol_version"] == 1

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(ack["beacon_id"]))
        receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

    assert beacon is not None
    assert beacon.protocol_version == 1
    assert beacon.protocol_session_id == receipt.session_id
    assert receipt.message_type == "REGISTER"


def test_protocol_task_result_frame_records_receipt(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client)
    frame = encode_protocol_test_frame(
        TASK_RESULT,
        {
            "beacon_id": registered["beacon_id"],
            "output_digest": "sha256:abc123",
            "status": "completed",
            "task_id": "task-one",
        },
    )

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    ack = decode_protocol_response(response.content)
    assert ack["acknowledged_message_type"] == "TASK_RESULT"
    assert ack["receipt"] == "stored"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

    assert receipt.beacon_id == uuid.UUID(registered["beacon_id"])
    assert receipt.message_type == "TASK_RESULT"


def test_protocol_hmac_tamper_rejected_and_logged(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=bytes(frame),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "HMAC_MISMATCH"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.hmac_mismatch"
    assert event.severity == "high"
    assert event.session_id
    assert event.nonce


def test_protocol_replay_nonce_rejected_and_logged(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = encode_protocol_test_frame(
        REGISTER,
        register_payload(supported_versions=[1]),
        nonce=bytes.fromhex("0a0b0c0d0e0f101112131415"),
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}

    first = protocol_c2_client.post("/api/v1/protocol/frames", content=frame, headers=headers)
    second = protocol_c2_client.post("/api/v1/protocol/frames", content=frame, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "REPLAY_DETECTED"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.replay_detected"


def test_security_events_endpoint_lists_protocol_events(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=bytes(frame),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    response = protocol_c2_client.get("/api/v1/security/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "protocol.hmac_mismatch"


def test_transport_status_requires_auth_and_reports_websocket_count(protocol_c2_client):
    unauthenticated = protocol_c2_client.get("/api/v1/transport")
    token = connect_c2(protocol_c2_client)

    assert unauthenticated.status_code == 401
    assert protocol_c2_client.get(
        "/api/v1/transport",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["active_websocket_connections"] == 0

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
        ack = decode_protocol_response(websocket.receive_bytes())
        assert ack["transport"] == "websocket"

        connected = protocol_c2_client.get("/api/v1/transport", headers={"Authorization": f"Bearer {token}"})
        assert connected.json()["active_websocket_connections"] == 1

    disconnected = protocol_c2_client.get("/api/v1/transport", headers={"Authorization": f"Bearer {token}"})
    assert disconnected.json()["active_websocket_connections"] == 0


def test_longpoll_holds_reports_active_rejects_duplicate_and_times_out(longpoll_c2_client):
    c2_token = connect_c2(longpoll_c2_client)
    registered = register_beacon(longpoll_c2_client)
    beacon_headers = {"Authorization": f"Bearer {registered['beacon_token']}"}
    c2_headers = {"Authorization": f"Bearer {c2_token}"}
    result: dict[str, object] = {}

    def hold_poll() -> None:
        result["response"] = longpoll_c2_client.get(
            f"/api/v1/beacons/{registered['beacon_id']}/poll?timeout_seconds=1",
            headers=beacon_headers,
        )

    thread = threading.Thread(target=hold_poll)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        active_status = None
        while time.monotonic() < deadline:
            active_status = longpoll_c2_client.get("/api/v1/transport", headers=c2_headers).json()
            if active_status["active_longpoll_requests"] == 1:
                break
            time.sleep(0.05)
        assert active_status is not None
        assert active_status["active_longpoll_requests"] == 1

        duplicate = longpoll_c2_client.get(
            f"/api/v1/beacons/{registered['beacon_id']}/poll?timeout_seconds=1",
            headers=beacon_headers,
        )
        assert duplicate.status_code == 409
    finally:
        thread.join(timeout=3)

    assert not thread.is_alive()
    response = result["response"]
    assert response.status_code == 204

    disconnected = longpoll_c2_client.get("/api/v1/transport", headers=c2_headers).json()
    assert disconnected["active_longpoll_requests"] == 0
    assert disconnected["transport_mode_counts"]["long-poll"] == 1

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert beacon is not None
    assert beacon.transport_mode == "long-poll"
    assert beacon.transport_connected is False


def test_longpoll_frame_post_decodes_shared_protocol_messages(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    headers = {"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"}
    heartbeat = encode_protocol_test_frame(
        HEARTBEAT,
        {"beacon_id": registered["beacon_id"], "hostname": "longpoll-heartbeat"},
    )
    poll = encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]})
    result = encode_protocol_test_frame(
        TASK_RESULT,
        {
            "beacon_id": registered["beacon_id"],
            "output_digest": "sha256:longpoll",
            "status": "completed",
            "task_id": "lp-task",
        },
    )

    heartbeat_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=heartbeat,
        headers=headers,
    )
    poll_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=poll,
        headers=headers,
    )
    result_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=result,
        headers=headers,
    )

    heartbeat_ack = decode_protocol_response(heartbeat_response.content)
    poll_ack = decode_protocol_response(poll_response.content)
    result_ack = decode_protocol_response(result_response.content)
    assert heartbeat_response.status_code == 200
    assert heartbeat_ack["acknowledged_message_type"] == "HEARTBEAT"
    assert heartbeat_ack["transport"] == "long-poll"
    assert poll_ack["task"] is None
    assert result_ack["receipt"] == "stored"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        receipts = session.execute(select(ProtocolFrameReceipt)).scalars().all()

    assert beacon is not None
    assert beacon.hostname == "longpoll-heartbeat"
    assert beacon.transport_mode == "long-poll"
    assert beacon.transport_connected is False
    assert [receipt.message_type for receipt in receipts] == ["HEARTBEAT", "TASK_POLL", "TASK_RESULT"]


def test_longpoll_frame_post_rejects_beacon_id_mismatch_with_encrypted_error(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    frame = encode_protocol_test_frame(TASK_POLL, {"beacon_id": str(uuid.uuid4())})

    response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=frame,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/octet-stream"
    error_payload = decode_protocol_response(response.content)
    assert error_payload["code"] == "BEACON_ID_MISMATCH"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.beacon_id_mismatch"
    assert event.beacon_id == uuid.UUID(registered["beacon_id"])


def test_longpoll_frame_post_hmac_tamper_and_replay_are_logged(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    headers = {"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"}

    tampered = bytearray(encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}))
    tampered[-1] ^= 0x01
    tampered_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=bytes(tampered),
        headers=headers,
    )

    replay = encode_protocol_test_frame(
        TASK_POLL,
        {"beacon_id": registered["beacon_id"]},
        nonce=bytes.fromhex("202122232425262728292a2b"),
    )
    frame_path = f"/api/v1/beacons/{registered['beacon_id']}/frame"
    first_replay = longpoll_c2_client.post(frame_path, content=replay, headers=headers)
    second_replay = longpoll_c2_client.post(frame_path, content=replay, headers=headers)

    assert tampered_response.status_code == 401
    assert tampered_response.json()["code"] == "HMAC_MISMATCH"
    assert first_replay.status_code == 200
    assert second_replay.status_code == 409
    assert second_replay.json()["code"] == "REPLAY_DETECTED"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event_types = {
            event.event_type
            for event in session.execute(
                select(ProtocolSecurityEvent).order_by(ProtocolSecurityEvent.occurred_at)
            ).scalars()
        }

    assert {"protocol.hmac_mismatch", "protocol.replay_detected"}.issubset(event_types)


def test_longpoll_frame_post_oversize_rejected_and_logged(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tiny-longpoll.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_LONGPOLL_MAX_FRAME_BYTES", "256")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(C2_DATABASE_URL=database_url, C2_BEACON_LONGPOLL_MAX_FRAME_BYTES="256")
    registered = register_beacon(client)

    response = client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=b"x" * 257,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "FRAME_TOO_LARGE"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.frame_too_large"


def test_beacon_websocket_registers_and_returns_encrypted_ack(protocol_c2_client):
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(frame)
        ack = decode_protocol_response(websocket.receive_bytes())

        assert ack["acknowledged_message_type"] == "REGISTER"
        assert ack["beacon_id"]
        assert ack["beacon_token"]
        assert ack["selected_protocol_version"] == 1
        assert ack["transport"] == "websocket"

        settings = get_settings()
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as session:
            beacon = session.get(Beacon, uuid.UUID(ack["beacon_id"]))
            receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

        assert beacon is not None
        assert beacon.transport_mode == "websocket"
        assert beacon.transport_connected is True
        assert beacon.transport_last_seen is not None
        assert receipt.message_type == "REGISTER"


def test_beacon_websocket_existing_beacon_authenticates_with_token(protocol_c2_client):
    registered = register_beacon(protocol_c2_client)
    frame = encode_protocol_test_frame(HEARTBEAT, {"beacon_id": registered["beacon_id"], "hostname": "ws-heartbeat"})

    with protocol_c2_client.websocket_connect(
        f"/ws/beacon?beacon_id={registered['beacon_id']}",
        subprotocols=["xero.beacon.v1", f"bearer.{registered['beacon_token']}"],
    ) as websocket:
        websocket.send_bytes(frame)
        ack = decode_protocol_response(websocket.receive_bytes())

        assert ack["acknowledged_message_type"] == "HEARTBEAT"
        assert ack["transport"] == "websocket"

        settings = get_settings()
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as session:
            beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

        assert beacon is not None
        assert beacon.hostname == "ws-heartbeat"
        assert beacon.transport_mode == "websocket"
        assert beacon.transport_connected is True


def test_beacon_websocket_rejects_text_frame(protocol_c2_client):
    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_text("not-binary")
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.text_frame_rejected"


def test_beacon_websocket_duplicate_connection_closes_prior(protocol_c2_client):
    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as first:
        first.send_bytes(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
        ack = decode_protocol_response(first.receive_bytes())

        with protocol_c2_client.websocket_connect(
            f"/ws/beacon?beacon_id={ack['beacon_id']}",
            subprotocols=["xero.beacon.v1", f"bearer.{ack['beacon_token']}"],
        ) as second:
            second.send_bytes(encode_protocol_test_frame(TASK_POLL, {"beacon_id": ack["beacon_id"]}))
            second_ack = decode_protocol_response(second.receive_bytes())
            assert second_ack["task"] is None

            with pytest.raises(WebSocketDisconnect) as disconnect:
                first.receive_bytes()

    assert disconnect.value.code == WS_CLOSE_DUPLICATE


def test_beacon_websocket_hmac_tamper_rejected_and_logged(protocol_c2_client):
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(bytes(frame))
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.hmac_mismatch"
    assert event.severity == "high"


def test_beacon_websocket_replay_nonce_rejected_and_logged(protocol_c2_client):
    frame = encode_protocol_test_frame(
        REGISTER,
        register_payload(supported_versions=[1]),
        nonce=bytes.fromhex("101112131415161718191a1b"),
    )

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(frame)
        decode_protocol_response(websocket.receive_bytes())
        websocket.send_bytes(frame)
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.replay_detected"


def test_beacon_websocket_oversize_frame_is_rejected_and_logged(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tiny-ws.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_WS_MAX_MESSAGE_BYTES", "256")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(C2_DATABASE_URL=database_url, C2_BEACON_WS_MAX_MESSAGE_BYTES="256")

    with client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(b"x" * 257)
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 1009


def test_beacon_transport_send_queue_backpressure_disconnects():
    class SlowWebSocket:
        application_state = WebSocketState.CONNECTED

        def __init__(self) -> None:
            self.closed_code: int | None = None

        async def send_bytes(self, _: bytes) -> None:
            await asyncio.sleep(60)

        async def close(self, *, code: int = 1000) -> None:
            self.closed_code = code
            self.application_state = WebSocketState.DISCONNECTED

    async def scenario() -> int | None:
        manager = BeaconTransportManager(queue_size=1)
        websocket = SlowWebSocket()
        connection = await manager.register(websocket, uuid.uuid4())
        assert await connection.enqueue(b"one")
        assert not await connection.enqueue(b"two")
        await manager.close_all()
        return websocket.closed_code

    assert asyncio.run(scenario()) == WS_CLOSE_OVERLOADED


def test_register_returns_one_time_token_and_list_is_token_free(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client)
    listed = c2_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})

    assert registered["beacon_token"]
    assert registered["sleep"] == 5
    assert registered["jitter"] == 0.25
    assert listed.status_code == 200
    assert listed.json()["items"][0]["hostname"] == "test-host"
    assert "beacon_token" not in listed.text
    assert "beacon_token_hash" not in listed.text


def test_duplicate_fingerprint_updates_one_row_and_rotates_token(c2_client):
    fingerprint = f"stable-{uuid.uuid4()}"
    first = register_beacon(c2_client, machine_fingerprint_hash=fingerprint, hostname="first-host")
    second = register_beacon(c2_client, machine_fingerprint_hash=fingerprint, hostname="second-host")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacons = session.execute(select(Beacon).where(Beacon.machine_fingerprint_hash == fingerprint)).scalars().all()

    assert first["beacon_id"] == second["beacon_id"]
    assert first["beacon_token"] != second["beacon_token"]
    assert len(beacons) == 1
    assert beacons[0].hostname == "second-host"


def test_invalid_beacon_ip_returns_422(c2_client):
    response = c2_client.post("/api/v1/beacons/register", json=register_payload(internal_ip="10.0.0.999"))

    assert response.status_code == 422


def test_heartbeat_updates_last_seen_and_metadata(c2_client):
    registered = register_beacon(c2_client)
    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={"hostname": "renamed-host", "internal_ip": "10.20.0.9", "pid": 3333},
    )

    assert response.status_code == 200
    assert response.json()["beacon"]["hostname"] == "renamed-host"
    assert response.json()["beacon"]["internal_ip"] == "10.20.0.9"


def test_heartbeat_rejects_unknown_or_invalid_token(c2_client):
    registered = register_beacon(c2_client)

    unknown = c2_client.post(
        f"/api/v1/beacons/{uuid.uuid4()}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={},
    )
    invalid = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": "Bearer wrong"},
        json={},
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 401


def test_list_beacons_filters_by_status(c2_client):
    token = connect_c2(c2_client)
    online = register_beacon(c2_client, hostname="online-host")
    offline = register_beacon(c2_client, hostname="offline-host")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(offline["beacon_id"]))
        assert beacon is not None
        beacon.status = BEACON_STATUS_OFFLINE
        session.add(beacon)
        session.commit()

    response = c2_client.get("/api/v1/beacons?status=online", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    hostnames = {item["hostname"] for item in response.json()["items"]}
    assert hostnames == {online["beacon"]["hostname"]}


def test_stale_detector_marks_beacons_offline_and_logs_event(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.last_seen = utc_now() - timedelta(seconds=60)
        session.add(beacon)
        session.commit()

    with SessionFactory() as session:
        stale = mark_stale_beacons_offline(session, settings, now=utc_now())
        session.commit()

    with SessionFactory() as session:
        event = session.execute(select(BeaconEvent)).scalar_one()
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert [item.hostname for item in stale] == ["test-host"]
    assert beacon is not None
    assert beacon.status == "offline"
    assert event.new_status == "offline"


def test_heartbeat_recovers_offline_beacon_and_logs_event(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.status = "offline"
        beacon.beacon_token_hash = hash_beacon_token(registered["beacon_token"])
        session.add(beacon)
        session.commit()

    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={},
    )

    with SessionFactory() as session:
        event = session.execute(select(BeaconEvent).where(BeaconEvent.new_status == "online")).scalar_one()

    assert response.status_code == 200
    assert response.json()["beacon"]["status"] == "online"
    assert event.old_status == "offline"
    assert event.reason == "heartbeat"


def test_infrastructure_workers_list_seeds_embedded_workers(c2_client):
    token = connect_c2(c2_client)

    response = c2_client.get("/api/v1/infrastructure/workers", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    workers = response.json()["items"]
    assert {(worker["kind"], worker["origin"]) for worker in workers} == {
        ("beacon-handler", "embedded"),
        ("scanner", "embedded"),
    }
    assert all(worker["status"] == "online" for worker in workers)
    assert "worker_token" not in response.text
    assert "worker_token_hash" not in response.text


def test_worker_pairing_registration_and_heartbeat_are_token_safe(c2_client):
    token = connect_c2(c2_client)
    pairing = c2_client.post(
        "/api/v1/infrastructure/pairing-tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "external scanner one"},
    )
    assert pairing.status_code == 200
    pairing_payload = pairing.json()
    assert pairing_payload["pairing_token"]
    assert "docker compose -f docker-compose.scanner.yml" in pairing_payload["command"]

    registered = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "scanner",
            "name": "external scanner one",
            "pairing_token": pairing_payload["pairing_token"],
            "endpoint": "http://scanner.local:8000",
            "capabilities": ["tcp-connect", "service-enumeration"],
            "capacity": 10,
            "current_load": 1,
            "version": "test",
        },
    )
    assert registered.status_code == 200
    registered_payload = registered.json()
    assert registered_payload["worker_token"]
    assert registered_payload["worker"]["origin"] == "external"
    assert registered_payload["worker"]["status"] == "online"

    reused = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "scanner",
            "name": "external scanner one",
            "pairing_token": pairing_payload["pairing_token"],
        },
    )
    assert reused.status_code == 401

    heartbeat = c2_client.post(
        f"/api/v1/infrastructure/workers/{registered_payload['worker_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered_payload['worker_token']}"},
        json={
            "endpoint": "http://scanner.local:8000",
            "capabilities": ["tcp-connect"],
            "capacity": 10,
            "current_load": 2,
            "version": "test2",
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["worker"]["current_load"] == 2

    listed = c2_client.get("/api/v1/infrastructure/workers", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert "worker_token" not in listed.text
    assert "worker_token_hash" not in listed.text


def test_worker_stale_detector_marks_external_worker_offline(c2_client):
    token = connect_c2(c2_client)
    pairing = c2_client.post(
        "/api/v1/infrastructure/pairing-tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "beacon-handler", "name": "edge handler"},
    ).json()
    registered = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "beacon-handler",
            "name": "edge handler",
            "pairing_token": pairing["pairing_token"],
            "capacity": 5,
        },
    ).json()

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        worker = session.get(InfrastructureWorker, uuid.UUID(registered["worker_id"]))
        assert worker is not None
        worker.last_seen = utc_now() - timedelta(seconds=120)
        session.add(worker)
        session.commit()

    with SessionFactory() as session:
        stale = mark_stale_workers(session, settings, now=utc_now())
        session.commit()

    with SessionFactory() as session:
        event = session.execute(
            select(WorkerEvent).where(WorkerEvent.event_type == "worker.status.changed")
        ).scalar_one()
        worker = session.get(InfrastructureWorker, uuid.UUID(registered["worker_id"]))

    assert [item.name for item in stale] == ["edge handler"]
    assert worker is not None
    assert worker.status == "offline"
    assert event.message.endswith("to offline.")


def test_launch_worker_requires_enabled_provisioning(c2_client):
    token = connect_c2(c2_client)

    response = c2_client.post(
        "/api/v1/infrastructure/workers/launch",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "managed scanner", "host_port": 18003},
    )

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_launch_worker_records_managed_worker_when_provisioning_succeeds(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'launch.db'}"
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_CONNECT_PASSWORD="connect-me",
        C2_JWT_SECRET_KEY="test-c2-jwt-secret-with-enough-length",
        C2_LOCAL_PROVISIONING_ENABLED="true",
    )
    token = connect_c2(client)

    def fake_launch_worker(settings, *, kind, name, worker_id, pairing_token, host_port):
        assert kind == "scanner"
        assert name == "managed scanner"
        assert pairing_token
        assert host_port == 18003
        return "xero-managed-scanner-test", "http://host.docker.internal:18003"

    monkeypatch.setattr("xero_c2.main.launch_worker", fake_launch_worker)

    response = client.post(
        "/api/v1/infrastructure/workers/launch",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "managed scanner", "host_port": 18003},
    )

    assert response.status_code == 200
    worker = response.json()["worker"]
    assert worker["origin"] == "c2-managed"
    assert worker["status"] == "starting"
    assert worker["managed_project"] == "xero-managed-scanner-test"
    assert worker["endpoint"] == "http://host.docker.internal:18003"
