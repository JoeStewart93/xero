from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from xero_c2.protocol.constants import (
    AES_GCM_TAG_LENGTH,
    CURRENT_PROTOCOL_VERSION,
    FRAME_HEADER,
    FRAME_HEADER_LENGTH,
    FRAME_HMAC_LENGTH,
    HKDF_INFO,
    PROTOCOL_MAGIC,
)

REGISTER = "REGISTER"
HEARTBEAT = "HEARTBEAT"
TASK_POLL = "TASK_POLL"
TASK_RESULT = "TASK_RESULT"
SESSION_DATA = "SESSION_DATA"
ACK = "ACK"
PROTOCOL_ERROR = "PROTOCOL_ERROR"


class MessageType(IntEnum):
    REGISTER = 1
    HEARTBEAT = 2
    TASK_POLL = 3
    TASK_RESULT = 4
    SESSION_DATA = 5
    ACK = 6
    PROTOCOL_ERROR = 7


MESSAGE_NAMES = {item.value: item.name for item in MessageType}
MESSAGE_VALUES = {item.name: item.value for item in MessageType}


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SessionKeys:
    encryption_key: bytes
    hmac_key: bytes


@dataclass(frozen=True)
class DecodedFrame:
    version: int
    message_type: str
    flags: int
    header_length: int
    payload_length: int
    session_id: uuid.UUID
    nonce: bytes
    sender_public_key: bytes
    payload: dict[str, Any]
    payload_digest: str


class ReplayWindow:
    def __init__(self) -> None:
        self._seen: set[tuple[uuid.UUID, bytes]] = set()

    def check_and_remember(self, session_id: uuid.UUID, nonce: bytes) -> None:
        key = (session_id, nonce)
        if key in self._seen:
            raise ProtocolError("REPLAY_DETECTED", "Replay nonce rejected")
        self._seen.add(key)


def canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode_payload(payload: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("INVALID_PAYLOAD", "Payload is not canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ProtocolError("INVALID_PAYLOAD", "Payload envelope must be an object")
    return decoded


def load_private_key(private_key_b64: str) -> x25519.X25519PrivateKey:
    try:
        private_bytes = base64.b64decode(private_key_b64, validate=True)
    except ValueError as exc:
        raise ProtocolError("INVALID_PRIVATE_KEY", "Protocol private key is not valid base64") from exc
    if len(private_bytes) != 32:
        raise ProtocolError("INVALID_PRIVATE_KEY", "Protocol private key must be 32 bytes")
    return x25519.X25519PrivateKey.from_private_bytes(private_bytes)


def public_key_bytes(private_key: x25519.X25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_b64(public_key: bytes) -> str:
    return base64.b64encode(public_key).decode("ascii")


def private_key_public_b64(private_key: x25519.X25519PrivateKey) -> str:
    return public_key_b64(public_key_bytes(private_key))


def _public_key_from_bytes(public_key: bytes) -> x25519.X25519PublicKey:
    if len(public_key) != 32:
        raise ProtocolError("INVALID_PUBLIC_KEY", "Sender public key must be 32 bytes")
    try:
        return x25519.X25519PublicKey.from_public_bytes(public_key)
    except ValueError as exc:
        raise ProtocolError("INVALID_PUBLIC_KEY", "Sender public key is invalid") from exc


def derive_session_keys(
    private_key: x25519.X25519PrivateKey,
    peer_public_key: bytes,
    session_id: uuid.UUID,
) -> SessionKeys:
    shared_secret = private_key.exchange(_public_key_from_bytes(peer_public_key))
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=session_id.bytes,
        info=HKDF_INFO,
    ).derive(shared_secret)
    return SessionKeys(encryption_key=derived[:32], hmac_key=derived[32:])


def _message_type_value(message_type: str | MessageType) -> int:
    if isinstance(message_type, MessageType):
        return int(message_type.value)
    normalized = message_type.upper()
    if normalized not in MESSAGE_VALUES:
        raise ProtocolError("UNKNOWN_MESSAGE_TYPE", f"Unknown message type {message_type}")
    return MESSAGE_VALUES[normalized]


def _message_type_name(message_type: int) -> str:
    if message_type not in MESSAGE_NAMES:
        raise ProtocolError("UNKNOWN_MESSAGE_TYPE", f"Unknown message type {message_type}")
    return MESSAGE_NAMES[message_type]


def _validate_version(version: int, supported_versions: list[int] | tuple[int, ...]) -> None:
    if version not in supported_versions:
        raise ProtocolError("UNSUPPORTED_VERSION", f"Unsupported protocol version {version}")


def encode_frame(
    *,
    private_key: x25519.X25519PrivateKey,
    peer_public_key: bytes,
    message_type: str | MessageType,
    payload: dict[str, Any],
    session_id: uuid.UUID | None = None,
    nonce: bytes | None = None,
    flags: int = 0,
    version: int = CURRENT_PROTOCOL_VERSION,
    max_frame_bytes: int = 1_048_576,
) -> bytes:
    if len(peer_public_key) != 32:
        raise ProtocolError("INVALID_PUBLIC_KEY", "Peer public key must be 32 bytes")
    if flags < 0 or flags > 255:
        raise ProtocolError("INVALID_FLAGS", "Frame flags must fit in one byte")
    session_uuid = session_id or uuid.uuid4()
    frame_nonce = nonce or secrets.token_bytes(12)
    if len(frame_nonce) != 12:
        raise ProtocolError("INVALID_NONCE", "Frame nonce must be 12 bytes")

    message_value = _message_type_value(message_type)
    payload_bytes = canonical_payload(payload)
    keys = derive_session_keys(private_key, peer_public_key, session_uuid)
    encrypted_payload = AESGCM(keys.encryption_key).encrypt(frame_nonce, payload_bytes, session_uuid.bytes)
    header = FRAME_HEADER.pack(
        PROTOCOL_MAGIC,
        version,
        message_value,
        flags,
        FRAME_HEADER_LENGTH,
        len(encrypted_payload),
        session_uuid.bytes,
        frame_nonce,
        public_key_bytes(private_key),
    )
    frame_without_hmac = header + encrypted_payload
    signature = hmac.new(keys.hmac_key, frame_without_hmac, hashlib.sha256).digest()
    frame = frame_without_hmac + signature
    if len(frame) > max_frame_bytes:
        raise ProtocolError("FRAME_TOO_LARGE", "Encoded frame exceeds configured maximum")
    return frame


def decode_frame(
    frame: bytes,
    *,
    private_key: x25519.X25519PrivateKey,
    supported_versions: list[int] | tuple[int, ...] = (CURRENT_PROTOCOL_VERSION,),
    max_frame_bytes: int = 1_048_576,
    replay_window: ReplayWindow | None = None,
) -> DecodedFrame:
    if len(frame) > max_frame_bytes:
        raise ProtocolError("FRAME_TOO_LARGE", "Frame exceeds configured maximum")
    minimum_length = FRAME_HEADER_LENGTH + AES_GCM_TAG_LENGTH + FRAME_HMAC_LENGTH
    if len(frame) < minimum_length:
        raise ProtocolError("MALFORMED_FRAME", "Frame is shorter than the minimum length")

    try:
        (
            magic,
            version,
            message_type,
            flags,
            header_length,
            payload_length,
            session_bytes,
            nonce,
            sender_public_key,
        ) = FRAME_HEADER.unpack(frame[:FRAME_HEADER_LENGTH])
    except struct.error as exc:  # type: ignore[name-defined]
        raise ProtocolError("MALFORMED_FRAME", "Frame header is malformed") from exc

    if magic != PROTOCOL_MAGIC:
        raise ProtocolError("MALFORMED_FRAME", "Frame magic is invalid")
    _validate_version(version, supported_versions)
    message_name = _message_type_name(message_type)
    if header_length != FRAME_HEADER_LENGTH:
        raise ProtocolError("MALFORMED_FRAME", "Frame header length is invalid")
    if payload_length < AES_GCM_TAG_LENGTH:
        raise ProtocolError("MALFORMED_FRAME", "Encrypted payload is shorter than the AES-GCM tag")
    expected_length = FRAME_HEADER_LENGTH + payload_length + FRAME_HMAC_LENGTH
    if len(frame) != expected_length:
        raise ProtocolError("MALFORMED_FRAME", "Frame payload length does not match frame size")

    session_id = uuid.UUID(bytes=session_bytes)
    if replay_window is not None:
        replay_window.check_and_remember(session_id, nonce)

    encrypted_payload = frame[FRAME_HEADER_LENGTH : FRAME_HEADER_LENGTH + payload_length]
    received_hmac = frame[FRAME_HEADER_LENGTH + payload_length :]
    keys = derive_session_keys(private_key, sender_public_key, session_id)
    expected_hmac = hmac.new(keys.hmac_key, frame[: FRAME_HEADER_LENGTH + payload_length], hashlib.sha256).digest()
    if not hmac.compare_digest(received_hmac, expected_hmac):
        raise ProtocolError("HMAC_MISMATCH", "Frame HMAC verification failed", status_code=401)

    try:
        payload_bytes = AESGCM(keys.encryption_key).decrypt(nonce, encrypted_payload, session_id.bytes)
    except InvalidTag as exc:
        raise ProtocolError("DECRYPT_FAILED", "Frame decrypt failed", status_code=400) from exc

    payload = decode_payload(payload_bytes)
    return DecodedFrame(
        version=version,
        message_type=message_name,
        flags=flags,
        header_length=header_length,
        payload_length=payload_length,
        session_id=session_id,
        nonce=nonce,
        sender_public_key=sender_public_key,
        payload=payload,
        payload_digest=hashlib.sha256(canonical_payload(payload)).hexdigest(),
    )
