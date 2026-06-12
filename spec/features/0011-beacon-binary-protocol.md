# F0011: Beacon Binary Protocol

## Metadata
| Field | Value |
|---|---|
| ID | F0011 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 2 |
| Depends on | F0004 |

## Summary
Custom binary frame format for beacon-to-C2/handler messages with X25519/HKDF session key derivation, AES-256-GCM encrypted payloads, HMAC-SHA256 integrity verification, typed message envelopes, replay protection, protocol receipts, and operator-visible security events.

## Requirements
- Custom binary frames ready for later TLS 1.3 transports
- X25519/HKDF-SHA256 session key derivation with AES-256-GCM payload encryption
- HMAC-SHA256 message authentication on every frame
- Message types: REGISTER, HEARTBEAT, TASK_POLL, TASK_RESULT, SESSION_DATA, ACK, PROTOCOL_ERROR
- Python encoder/decoder library plus Go vector-compatibility package
- Development/test C2 validation harness with redacted protocol security events

## Stages

### Stage 1: Frame specification
**Goal:** Define wire format: header, nonce, ciphertext, HMAC.
**Acceptance Criteria:**
- [x] Frame header includes version, message_type, payload_length
- [x] Nonce unique per message; replay window rejects duplicates
- [x] spec/architecture/protocol-stack.md documents frame layout

### Stage 2: Crypto primitives
**Goal:** Implement AES-GCM encrypt/decrypt and HMAC sign/verify.
**Acceptance Criteria:**
- [x] Session key derived from registration handshake
- [x] Decrypt failure returns PROTOCOL_ERROR without crash
- [x] HMAC mismatch rejects frame and logs security event

### Stage 3: Codec library
**Goal:** Python and Go codec with round-trip test vectors.
**Acceptance Criteria:**
- [x] `platform/services/c2-api/xero_c2/protocol/codec.py` encode/decode all message types
- [x] Go protocol codec mirrors Python test vectors byte-for-byte
- [x] Malformed-frame corpus handles invalid frames gracefully

### Stage 4: C2 harness and observability
**Goal:** Validate binary frames through C2 without implementing live beacon transports.
**Acceptance Criteria:**
- [x] `GET /api/v1/protocol` advertises v1 metadata and C2 public key
- [x] `POST /api/v1/protocol/frames` records REGISTER metadata and TASK_RESULT receipts
- [x] Invalid frames return protocol errors and record redacted security events without 500s
- [x] Settings/C2 displays protocol status and security events
- [x] Beacon detail displays protocol version after binary registration

## Feature Acceptance Criteria

- [x] Encode/decode round-trip passes for all message types
- [x] Tampered HMAC frame rejected with logged security event
- [x] Protocol version negotiation supported in REGISTER response

## Test Plan

### Unit Tests
- [x] test_frame_encode_decode_roundtrip
- [x] test_hmac_tamper_rejected
- [x] test_replay_nonce_rejected
- [x] test_unknown_message_type_error
- [x] test_session_key_derivation
- [x] test_go_python_vector_compatibility

### System / Integration Tests
- [x] Backend decodes REGISTER frame from test beacon fixture
- [x] Encrypted TASK_RESULT frame stored and acknowledged
- [x] Invalid frame does not crash backend process

### Playwright Tests
- [x] Settings protocol version displays current supported version
- [x] Security events panel shows HMAC failure alert when injected
- [x] Beacon detail shows protocol version from registration

## Validation

- Backend lint, unit, behave, integration, and OpenAPI check pass.
- Go protocol vector compatibility passes with local Go when present or Docker `golang:1.26` fallback.
- Frontend lint, unit, build, Playwright E2E, and live Browser sanity validation pass.
