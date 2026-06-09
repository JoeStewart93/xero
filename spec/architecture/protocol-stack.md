# Protocol Stack

## Current Operator and Service Layers

```text
Operator UI
  -> HTTPS/TLS in deployed environments
  -> Local Xero BFF REST API + local operator JWT

Operator UI Settings
  -> HTTPS/TLS in deployed environments
  -> Xero C2 Backend /api/v1/c2/connect
  -> C2 bearer token stored in browser connection context

Operator UI Realtime
  -> WebSocket /ws/operator on Xero C2 Backend
  -> C2 bearer token via WebSocket subprotocol, Authorization header, or query fallback
  -> JSON events from Redis events:operator

Beacon
  -> TLS 1.3
  -> External handler (P1) or Xero C2 Backend embedded handler directly (default)
  -> WebSocket primary or HTTP long-poll fallback
  -> Custom binary frames with encrypted payloads

Scanner
  -> Xero C2 Backend embedded scanner by default
  -> External scanner worker control plane later
  -> Scan shards, progress events, and merged results

Beacon pivot
  -> Later beacon-hosted scanner/proxy route
  -> Explicit project scope and audit metadata required
```

## UI -> Local BFF

- **Transport:** HTTP locally, HTTPS/TLS in deployed environments.
- **API:** REST.
- **Auth:** JWT bearer token issued by `POST /auth/login`. ([F0003](../features/0003-operator-authentication.md))
- **Protected health:** `/api/v1/health` and `/api/v1/ready`.
- **Current operator endpoints:** `/api/v1/me`, `/api/v1/beacons`, `/api/v1/auth/password`.

## UI -> C2 Backend

- **Transport:** HTTP locally, HTTPS/TLS in deployed environments.
- **Connection auth:** `POST /api/v1/c2/connect` with `C2_CONNECT_PASSWORD`.
- **Session check:** `GET /api/v1/c2/session` with returned C2 bearer token.
- **Operator realtime:** `GET /ws/operator` WebSocket on the C2 service role with protocol `xero.operator.v1` and C2 bearer token.
- **Realtime events:** Versioned JSON envelopes published on Redis channel `events:operator`, including `beacon.registered`, `beacon.heartbeat`, `beacon.status.changed`, `system.realtime.degraded`, and `system.realtime.recovered`.
- **Beacon registration:** `POST /api/v1/beacons/register` is available on the C2 role without operator JWT. It validates metadata, creates or updates one row per machine fingerprint, returns a plaintext opaque `beacon_token` once, and persists only a SHA-256 token hash. `GET /api/v1/beacons` requires a valid C2 token on the C2 role or a local operator JWT on the BFF role and never returns token material.
- **Beacon heartbeat:** `POST /api/v1/beacons/{beacon_id}/heartbeat` is C2-role only and uses the plaintext opaque beacon token as a bearer credential. Heartbeats update `last_seen`, restore `status=online`, may update runtime metadata, return sleep/jitter profile values, and publish `beacon.heartbeat`. Offline/online status transitions publish `beacon.status.changed` and are logged in `beacon_events`.
- **Beacon listing/detail:** `GET /api/v1/beacons` supports `?status=online|offline`; `GET /api/v1/beacons/{beacon_id}` returns token-free public beacon detail.
- **Role requirement:** C2 connection endpoints return conflict unless `XERO_SERVICE_ROLE=c2`.

### Operator WebSocket Close Codes

| Code | Meaning |
| :--- | :--- |
| `4401` | Missing, invalid, or expired authentication token |
| `4403` | Origin is forbidden or service role is not C2 |
| `1013` | Realtime service is temporarily overloaded or unavailable |

## Beacon -> C2/Handler

| Layer | Technology | Feature |
| :--- | :--- | :--- |
| Binary framing | Custom protocol | [F0011](../features/0011-beacon-binary-protocol.md) |
| Primary transport | WebSocket over TLS 1.3 | [F0012](../features/0012-beacon-websocket-transport.md) |
| Fallback transport | HTTP long-polling | [F0013](../features/0013-beacon-http-longpoll-fallback.md) |
| Registration token | Opaque per-beacon token returned once; SHA-256 hash stored | [F0009](../features/0009-beacon-registration.md) |
| Heartbeat keepalive | Token-authenticated heartbeat endpoint with stale/offline monitor | [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| Encryption | AES-256-GCM payloads | F0011 |
| Key exchange | RSA-4096 or ECC | F0011 |
| Integrity | HMAC-SHA256 | F0011 |

## Handler -> C2 Backend

- Encrypted outbound tunnel with certificate pinning (SR-03).
- Beacon mTLS when connecting through handlers (FR-18).
- Handler registration, heartbeat, health, capacity, connected beacon count, draining state, and beacon assignment are planned control-plane messages.
- Handler pools route beacons to healthy handlers and mark affected beacons for migration when a handler goes unhealthy.

**Features:** [F0039](../features/0039-handler-tunnel-to-core.md), [F0109](../features/0109-handler-load-balancing.md)

## Scanner Worker -> C2 Backend

- The C2 backend remains the embedded scanner default for local and single-server deployments.
- External scanner workers later register with C2, report heartbeat/capacity/capabilities, receive scan jobs or shards, stream progress, and submit structured results.
- The planned scan request model supports execution targets: `auto`, a specific scanner worker, a distributed scanner pool, and later a beacon pivot route.
- Distributed scan results are merged into one operator-visible result set with shard provenance retained for audit/debugging.

**Features:** [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Beacon Pivot Scanner/Proxy -> C2 Backend

- Pivot scanning/proxying is a later capability where an installed beacon acts as the scan/proxy vantage point for approved project scope.
- Pivot jobs use the same operator-visible scan/result model as scanner workers but add beacon identity, route, operator, and project-scope audit fields.

**Feature:** [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)

## Traffic Shaping

Beacon traffic will be configurable to mimic legitimate services such as CDN or analytics traffic. See [F0021](../features/0021-traffic-shaping-profiles.md) and [F0040](../features/0040-handler-traffic-masking.md).

## Future

Wire-format specification (`spec/protocol.md`) will be authored when F0011 implementation begins.
