# Protocol Stack

## Current Operator and Service Layers

```text
Operator UI
  -> HTTPS/TLS in deployed environments
  -> Local Xero BFF REST API + bootstrap JWT (setup/health only)

Operator UI Login (when C2 URL configured)
  -> HTTPS/TLS in deployed environments
  -> Xero C2 Backend POST /api/v1/auth/login
  -> C2 operator JWT stored as session + C2 connection context

Operator UI Realtime
  -> WebSocket /ws/operator on Xero C2 Backend
  -> C2 operator JWT via WebSocket subprotocol, Authorization header, or query fallback
  -> JSON events from Redis events:operator

Beacon
  -> TLS 1.3
  -> External handler (P1) or Xero C2 Backend embedded handler directly (default)
  -> WebSocket primary or HTTP long-poll fallback
  -> Custom binary frames with encrypted payloads

Scanner
  -> Xero C2 Backend embedded scanner by default
  -> External scanner worker pairing/heartbeat control plane
  -> Scan shards, progress events, and merged results later

Beacon pivot
  -> Later beacon-hosted scanner/proxy route
  -> Explicit project scope and audit metadata required
```

## UI -> Local BFF

- **Transport:** HTTP locally, HTTPS/TLS in deployed environments.
- **API:** REST.
- **Auth:** JWT bearer token issued by `POST /auth/login` for bootstrap scope only. ([F0003](../features/0003-operator-authentication.md), [F0074](../features/0074-c2-operator-authentication.md))
- **Protected health:** `/api/v1/health` and `/api/v1/ready`.
- **Current operator endpoints:** `/api/v1/me`, `/api/v1/auth/password`.

## UI -> C2 Backend

- **Transport:** HTTP locally, HTTPS/TLS in deployed environments.
- **Operator auth:** `POST /api/v1/auth/login` with C2 operator credentials; returns operator JWT with `kind: operator-session`. ([F0074](../features/0074-c2-operator-authentication.md))
- **Session check:** `GET /api/v1/me` or session endpoint with operator JWT.
- **Operator realtime:** `GET /ws/operator` WebSocket on the C2 API with protocol `xero.operator.v1` and C2 operator JWT.
- **Realtime events:** Versioned JSON envelopes published on Redis channel `events:operator`, including `beacon.registered`, `beacon.heartbeat`, `beacon.status.changed`, `system.realtime.degraded`, and `system.realtime.recovered`.
- **Beacon registration:** `POST /api/v1/beacons/register` is available on the C2 API without operator JWT. It validates metadata, creates or updates one row per machine fingerprint, returns a plaintext opaque `beacon_token` once, and persists only a SHA-256 token hash.
- **Beacon heartbeat:** `POST /api/v1/beacons/{beacon_id}/heartbeat` is C2-only and uses the plaintext opaque beacon token as a bearer credential. Heartbeats update `last_seen`, restore `status=online`, may update runtime metadata, return sleep/jitter profile values, and publish `beacon.heartbeat`. Offline/online status transitions publish `beacon.status.changed` and are logged in `beacon_events`.
- **Beacon listing/detail:** `GET /api/v1/beacons` supports `?status=online|offline`; `GET /api/v1/beacons/{beacon_id}` returns token-free public beacon detail. Both require a valid C2 operator JWT.
- **Beacon WebSocket transport:** `GET /ws/beacon` accepts binary F0011 frames with subprotocol `xero.beacon.v1`. New beacons REGISTER first and receive an encrypted ACK with beacon identity and one-time token. Existing beacons reconnect with `beacon_id` and bearer beacon token.
- **Transport status:** `GET /api/v1/transport` returns active beacon WebSocket connection count and configured WebSocket queue, timeout, ping, and max-message limits. It requires a valid C2 operator JWT.
- **Infrastructure workers:** `GET /api/v1/infrastructure/workers` returns embedded, external, and C2-managed handler/scanner worker inventory. `POST /api/v1/infrastructure/pairing-tokens` issues one-time external worker pairing tokens. Both require a valid C2 operator JWT.
- **Worker registration and heartbeat:** `POST /api/v1/infrastructure/workers/register` validates a one-time pairing token and returns a plaintext opaque worker token once. `POST /api/v1/infrastructure/workers/{worker_id}/heartbeat` uses that worker token as a bearer credential and updates status, endpoint, capacity, load, capabilities, and last heartbeat.
- **Local worker provisioning:** `POST /api/v1/infrastructure/workers/launch` and `POST /api/v1/infrastructure/workers/{worker_id}/stop` manage C2-managed scaffold workers when local provisioning is enabled.

### Operator WebSocket Close Codes

| Code | Meaning |
| :--- | :--- |
| `4401` | Missing, invalid, or expired authentication token |
| `4403` | Origin is forbidden |
| `1013` | Realtime service is temporarily overloaded or unavailable |

## Beacon -> C2/Handler

| Layer | Technology | Feature |
| :--- | :--- | :--- |
| Binary framing | Custom protocol | [F0011](../features/0011-beacon-binary-protocol.md) |
| Primary transport | WebSocket over TLS 1.3 | [F0012](../features/0012-beacon-websocket-transport.md) |
| Fallback transport | HTTP long-polling | [F0013](../features/0013-beacon-http-longpoll-fallback.md) |
| Registration token | Opaque per-beacon token returned once; SHA-256 hash stored | [F0009](../features/0009-beacon-registration.md) |
| Heartbeat keepalive | Token-authenticated heartbeat endpoint with stale/offline monitor | [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| Encryption | AES-256-GCM payloads | [F0011](../features/0011-beacon-binary-protocol.md) |
| Key exchange | X25519 with HKDF-SHA256 | [F0011](../features/0011-beacon-binary-protocol.md) |
| Integrity | HMAC-SHA256 | F0011 |

F0011 defines the reusable v1 frame layout in [spec/protocol.md](../protocol.md). Frames use a 72-byte fixed header, raw X25519 sender public keys, a 12-byte per-message nonce, encrypted canonical JSON envelopes, and HMAC-SHA256 over the header plus encrypted payload. C2 rejects duplicate session/nonce pairs and records redacted protocol security events for malformed, replayed, tampered, or undecryptable frames.

Current C2 protocol endpoints:

- `GET /api/v1/protocol`: operator-JWT protected protocol metadata and C2 public key.
- `POST /api/v1/protocol/frames`: development/test frame validation harness, enabled only with `C2_PROTOCOL_FRAME_HARNESS_ENABLED=true`.
- `GET /api/v1/security/events`: recent redacted protocol security events for operator visibility.
- `GET /api/v1/transport`: operator-JWT protected WebSocket transport status and configured limits.

**Removed by F0074:** `POST /api/v1/c2/connect`, shared `C2_CONNECT_PASSWORD`, and anonymous `kind: c2-connect` JWTs.

Current beacon WebSocket behavior:

- New beacons connect to `/ws/beacon` with subprotocol `xero.beacon.v1`, send encrypted `REGISTER` within 5 seconds, and receive encrypted ACK with `beacon_id`, one-time `beacon_token`, selected protocol version, sleep, jitter, and `transport=websocket`.
- Existing beacons reconnect with `?beacon_id=<uuid>` plus bearer token in `Authorization` or `Sec-WebSocket-Protocol: xero.beacon.v1,bearer.<token>`.
- Duplicate connections for the same beacon close the older socket with close code `4409`; disconnect clears only the matching active connection and leaves offline status to heartbeat stale logic.
- Text, malformed, replayed, tampered, and oversized frames record redacted security events and close without 500s. Oversized WebSocket messages close with `1009`.
- `HEARTBEAT` updates heartbeat, protocol, and transport timestamps. `TASK_POLL` dispatches the highest-priority queued task or returns `task: null`. `TASK_RESULT` records protocol receipts and updates known task lifecycle state until F0017 owns full result storage.

## Handler -> C2 Backend

- Encrypted outbound tunnel with certificate pinning (SR-03).
- Beacon mTLS when connecting through handlers (FR-18).
- Handler identity pairing, worker heartbeat, health, and capacity are implemented through the F0049 infrastructure worker HTTP control plane.
- Handler tunnel registration, connected beacon count, draining state, frame relay, and beacon assignment are planned tunnel messages.
- Handler pools route beacons to healthy handlers and mark affected beacons for migration when a handler goes unhealthy.

**Features:** [F0049](../features/0049-c2-infrastructure-worker-pairing.md), [F0039](../features/0039-handler-tunnel-to-core.md), [F0109](../features/0109-handler-load-balancing.md)

## Scanner Worker -> C2 Backend

- The C2 backend remains the embedded scanner default for local and single-server deployments.
- External scanner workers can register with C2 through one-time pairing tokens and report heartbeat/capacity/capabilities through the F0049 worker control plane.
- Scanner workers later receive scan jobs or shards, stream progress, and submit structured results.
- The planned scan request model supports execution targets: `auto`, a specific scanner worker, a distributed scanner pool, and later a beacon pivot route.
- Distributed scan results are merged into one operator-visible result set with shard provenance retained for audit/debugging.

**Features:** [F0049](../features/0049-c2-infrastructure-worker-pairing.md), [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Beacon Pivot Scanner/Proxy -> C2 Backend

- Pivot scanning/proxying is a later capability where an installed beacon acts as the scan/proxy vantage point for approved project scope.
- Pivot jobs use the same operator-visible scan/result model as scanner workers but add beacon identity, route, operator, and project-scope audit fields.

**Feature:** [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)

## Traffic Shaping

Beacon traffic will be configurable to mimic legitimate services such as CDN or analytics traffic. See [F0021](../features/0021-traffic-shaping-profiles.md) and [F0040](../features/0040-handler-traffic-masking.md).

## Future

F0012 and F0013 carry F0011 binary frames over beacon WebSocket and HTTP long-poll transports. F0014 adds queued task dispatch and lifecycle state. F0017 adds full result persistence semantics.
