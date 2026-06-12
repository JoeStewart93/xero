from __future__ import annotations

import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import x25519
from xero_c2.protocol import (
    ACK,
    HEARTBEAT,
    REGISTER,
    SESSION_DATA,
    TASK_POLL,
    TASK_RESULT,
    ProtocolError,
    ReplayWindow,
    decode_frame,
    derive_session_keys,
    encode_frame,
)
from xero_c2.protocol.codec import public_key_bytes


def private_key(seed: int) -> x25519.X25519PrivateKey:
    return x25519.X25519PrivateKey.from_private_bytes(bytes([seed]) * 32)


def round_trip(message_type: str, payload: dict) -> dict:
    server = private_key(1)
    client = private_key(2)
    session_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    nonce = bytes.fromhex("0102030405060708090a0b0c")
    frame = encode_frame(
        private_key=client,
        peer_public_key=public_key_bytes(server),
        message_type=message_type,
        payload=payload,
        session_id=session_id,
        nonce=nonce,
    )
    decoded = decode_frame(frame, private_key=server)
    assert decoded.message_type == message_type
    assert decoded.session_id == session_id
    assert decoded.nonce == nonce
    return decoded.payload


def test_frame_encode_decode_roundtrip_all_message_types():
    payloads = {
        REGISTER: {
            "architecture": "x64",
            "hostname": "protocol-host",
            "internal_ip": "10.10.0.10",
            "machine_fingerprint_hash": "protocol-fingerprint",
            "os": "Windows 11",
            "pid": 4242,
            "supported_versions": [1],
        },
        HEARTBEAT: {"beacon_id": str(uuid.uuid4())},
        TASK_POLL: {"beacon_id": str(uuid.uuid4())},
        TASK_RESULT: {"beacon_id": str(uuid.uuid4()), "status": "completed", "task_id": "task-1"},
        SESSION_DATA: {"beacon_id": str(uuid.uuid4()), "stream": "stdout", "chunk": "hello"},
        ACK: {"status": "ok"},
    }

    for message_type, payload in payloads.items():
        assert round_trip(message_type, payload) == payload


def test_hmac_tamper_rejected():
    server = private_key(1)
    client = private_key(2)
    frame = bytearray(
        encode_frame(
            private_key=client,
            peer_public_key=public_key_bytes(server),
            message_type=HEARTBEAT,
            payload={"beacon_id": str(uuid.uuid4())},
        )
    )
    frame[-1] ^= 0x01

    with pytest.raises(ProtocolError, match="HMAC"):
        decode_frame(bytes(frame), private_key=server)


def test_replay_nonce_rejected():
    server = private_key(1)
    client = private_key(2)
    replay_window = ReplayWindow()
    frame = encode_frame(
        private_key=client,
        peer_public_key=public_key_bytes(server),
        message_type=TASK_POLL,
        payload={"beacon_id": str(uuid.uuid4())},
    )

    decode_frame(frame, private_key=server, replay_window=replay_window)
    with pytest.raises(ProtocolError, match="Replay"):
        decode_frame(frame, private_key=server, replay_window=replay_window)


def test_unknown_message_type_error():
    server = private_key(1)
    client = private_key(2)
    frame = bytearray(
        encode_frame(
            private_key=client,
            peer_public_key=public_key_bytes(server),
            message_type=HEARTBEAT,
            payload={"beacon_id": str(uuid.uuid4())},
        )
    )
    frame[5] = 250

    with pytest.raises(ProtocolError) as exc:
        decode_frame(bytes(frame), private_key=server)

    assert exc.value.code == "UNKNOWN_MESSAGE_TYPE"


def test_session_key_derivation_is_deterministic():
    server = private_key(1)
    client = private_key(2)
    session_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    first = derive_session_keys(server, public_key_bytes(client), session_id)
    second = derive_session_keys(server, public_key_bytes(client), session_id)

    assert first == second
    assert len(first.encryption_key) == 32
    assert len(first.hmac_key) == 32


def test_malformed_frames_raise_protocol_error():
    server = private_key(1)

    for frame in (b"", b"nope", b"XERO\x01"):
        with pytest.raises(ProtocolError):
            decode_frame(frame, private_key=server)
