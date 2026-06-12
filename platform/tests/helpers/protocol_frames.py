from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cryptography.hazmat.primitives.asymmetric import x25519
from xero_c2.config import get_settings
from xero_c2.protocol import ACK, decode_frame, encode_frame, load_private_key
from xero_c2.protocol.codec import public_key_bytes


def protocol_client_private_key() -> x25519.X25519PrivateKey:
    return x25519.X25519PrivateKey.from_private_bytes(bytes([2]) * 32)


def c2_protocol_public_key_from_settings() -> bytes:
    settings = get_settings()
    return public_key_bytes(load_private_key(settings.protocol_private_key_b64))


def encode_protocol_test_frame(
    message_type: str,
    payload: Mapping[str, Any],
    *,
    max_frame_bytes: int | None = None,
    nonce: bytes | None = None,
    peer_public_key: bytes | None = None,
) -> bytes:
    settings = get_settings()
    return encode_frame(
        private_key=protocol_client_private_key(),
        peer_public_key=peer_public_key or c2_protocol_public_key_from_settings(),
        message_type=message_type,
        payload=dict(payload),
        nonce=nonce,
        max_frame_bytes=max_frame_bytes or settings.protocol_max_frame_bytes,
    )


def decode_protocol_response(frame: bytes, *, expected_message_type: str | None = None) -> dict:
    decoded = decode_frame(frame, private_key=protocol_client_private_key())
    if expected_message_type is not None:
        assert decoded.message_type == expected_message_type
    return decoded.payload


def decode_protocol_ack(frame: bytes) -> dict:
    return decode_protocol_response(frame, expected_message_type=ACK)
