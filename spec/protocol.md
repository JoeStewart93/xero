# Xero Beacon Binary Protocol

## Version

Current protocol version: `1`.

The F0011 protocol layer defines binary frames and encrypted JSON envelopes. F0012 carries these frames over the primary beacon WebSocket transport; the later F0013 long-poll fallback reuses the same wire contract.

## Frame Layout

All integer fields are network byte order. The fixed header length is 72 bytes.

| Field | Size | Description |
| :--- | ---: | :--- |
| `magic` | 4 | ASCII `XERO` |
| `version` | 1 | Protocol version, currently `1` |
| `message_type` | 1 | Numeric message type |
| `flags` | 1 | Reserved, currently `0` |
| `header_len` | 1 | Fixed header length, currently `72` |
| `payload_length` | 4 | AES-GCM ciphertext plus tag length |
| `session_id` | 16 | UUID bytes used as HKDF salt and AES-GCM AAD |
| `nonce` | 12 | AES-GCM nonce, unique per session |
| `sender_public_key` | 32 | Raw X25519 public key |
| `ciphertext_and_tag` | variable | Encrypted canonical JSON envelope |
| `hmac` | 32 | HMAC-SHA256 over header plus ciphertext/tag |

## Message Types

| Value | Name |
| ---: | :--- |
| 1 | `REGISTER` |
| 2 | `HEARTBEAT` |
| 3 | `TASK_POLL` |
| 4 | `TASK_RESULT` |
| 5 | `SESSION_DATA` |
| 6 | `ACK` |
| 7 | `PROTOCOL_ERROR` |

## Cryptography

- Key exchange: X25519.
- Key derivation: HKDF-SHA256, length 64, salt `session_id`, info `xero-protocol-v1`.
- Derived bytes `0..31` are the AES-256-GCM key.
- Derived bytes `32..63` are the HMAC-SHA256 key.
- AES-GCM additional authenticated data is the raw `session_id`.
- Payloads are compact canonical JSON with sorted object keys.

## Replay And Errors

Receivers reject duplicate `session_id` plus `nonce` pairs. HMAC failures, replay attempts, unsupported versions, unknown message types, malformed frames, and decrypt failures produce `PROTOCOL_ERROR` handling and redacted C2 security events. Security events must not store plaintext payloads, tokens, or key material.

## C2 Harness

F0011 adds a development/test validation harness:

- `GET /api/v1/protocol` returns C2 protocol metadata and public key.
- `POST /api/v1/protocol/frames` accepts binary frames only when `C2_PROTOCOL_FRAME_HARNESS_ENABLED=true`.
- `GET /api/v1/security/events` lists recent protocol validation failures for operator visibility.

The harness does not replace live transports.

## WebSocket Transport

F0012 adds `GET /ws/beacon` as the primary live beacon transport. Clients must use subprotocol `xero.beacon.v1` and binary WebSocket messages. New beacons send encrypted `REGISTER` as the first frame and receive an encrypted `ACK` containing `beacon_id`, one-time `beacon_token`, selected protocol version, sleep, jitter, and `transport=websocket`. Existing beacons reconnect with `beacon_id` and a bearer beacon token via the `Authorization` header or `bearer.<token>` WebSocket subprotocol.

The C2 backend shares F0011 decoding, replay checks, receipt recording, REGISTER handling, ACK creation, and redacted security-event logging between the HTTP harness and live transports. Valid inbound frames receive encrypted ACKs. `TASK_POLL` returns the highest-priority queued task for that beacon or `task: null` when no work is pending. `TASK_RESULT` records a protocol frame receipt, updates known task lifecycle status, and returns `receipt=stored`; full task-result body storage remains F0017.

## Task Queue Payloads

F0014 task ACKs are encrypted `ACK` frames with `acknowledged_message_type="TASK_POLL"` and either `task=null` or:

```json
{
  "id": "task uuid",
  "beacon_id": "beacon uuid",
  "module": "shell",
  "args": {
    "command": "whoami",
    "shell_type": "auto",
    "timeout_seconds": 60
  },
  "priority": "normal",
  "status": "dispatched"
}
```

`TASK_RESULT` frames may include `task_id` and `status` values `running`, `completed`, `failed`, `ok`, or `error`. Known task IDs update task lifecycle state; unknown task IDs still produce protocol receipts for backward compatibility. stdout, stderr, exit codes, chunks, and downloadable result bodies are not persisted until F0017.

`GET /api/v1/transport` is C2-token protected and reports active WebSocket beacon connections plus configured queue, timeout, ping, and max-message limits. Public `/health` and `/ready` remain container health contracts.
