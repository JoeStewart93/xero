# F0011: Beacon Binary Protocol

## Metadata
| Field | Value |
|---|---|
| ID | F0011 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 2 |
| Depends on | F0004 |

## Summary
Custom binary frame format for beacon-to-C2/handler messages with AES-256-GCM encrypted payloads, HMAC-SHA256 integrity verification, and typed message envelopes for tasks, results, and sessions.

## Requirements
- Custom binary frames over TLS 1.3 transport
- AES-256-GCM payload encryption with per-beacon session keys
- HMAC-SHA256 message authentication on every frame
- Message types: REGISTER, HEARTBEAT, TASK_POLL, TASK_RESULT, SESSION_DATA
- Python encoder/decoder library shared by backend and beacon tests

## Stages

### Stage 1: Frame specification
**Goal:** Define wire format: header, nonce, ciphertext, HMAC.
**Acceptance Criteria:**
- [ ] Frame header includes version, message_type, payload_length
- [ ] Nonce unique per message; replay window rejects duplicates
- [ ] spec/architecture/protocol-stack.md documents frame layout

### Stage 2: Crypto primitives
**Goal:** Implement AES-GCM encrypt/decrypt and HMAC sign/verify.
**Acceptance Criteria:**
- [ ] Session key derived from registration handshake
- [ ] Decrypt failure returns PROTOCOL_ERROR without crash
- [ ] HMAC mismatch rejects frame and logs security event

### Stage 3: Codec library
**Goal:** Python and Go codec with round-trip test vectors.
**Acceptance Criteria:**
- [ ] platform/backend/app/protocol/codec.py encode/decode all message types
- [ ] Go beacon codec mirrors Python test vectors byte-for-byte
- [ ] Fuzz test handles malformed frames gracefully

## Feature Acceptance Criteria

- [ ] Encode/decode round-trip passes for all message types
- [ ] Tampered HMAC frame rejected with logged security event
- [ ] Protocol version negotiation supported in REGISTER response

## Test Plan

### Unit Tests
- [ ] test_frame_encode_decode_roundtrip
- [ ] test_hmac_tamper_rejected
- [ ] test_replay_nonce_rejected
- [ ] test_unknown_message_type_error
- [ ] test_session_key_derivation
- [ ] test_go_python_vector_compatibility

### System / Integration Tests
- [ ] Backend decodes REGISTER frame from test beacon fixture
- [ ] Encrypted TASK_RESULT frame stored and acknowledged
- [ ] Invalid frame does not crash backend process

### Playwright Tests
- [ ] Settings protocol version displays current supported version
- [ ] Security events panel shows HMAC failure alert when injected
- [ ] Beacon detail shows protocol version from registration
