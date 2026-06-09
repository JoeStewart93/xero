# Components

## Xero UI

React + TypeScript + Tailwind web dashboard for operators. It is served by the frontend container and talks to the local BFF using `VITE_API_BASE_URL`.

**Current responsibilities:** Login screen, authenticated app shell, direct C2 operator realtime client/status, Home overview, Projects foundation, Recon foundation, C2-backed Beacons registry/detail route, Settings C2 connection workflow, protected Health page, and planned side tabs for Reporting, Inventory, and Assets.

**Features:** [F0007](../features/0007-react-ui-shell.md), [F0024](../features/0024-dashboard-ui.md)-[F0028](../features/0028-module-browser-ui.md)

## Local Xero BFF

FastAPI backend-for-frontend service running with `XERO_SERVICE_ROLE=bff`. It is local to the UI stack and does not own full C2 tasking behavior.

**Current responsibilities:** Operator login, JWT issuance, PostgreSQL-backed user records, default development operator/admin seeding, protected local health/readiness, local `/api/v1/beacons` compatibility listing, password change, CORS, and OpenAPI generation.

**Current public interfaces:**

- `POST /auth/login`
- `GET /health`
- `GET /ready`
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/me`
- `GET /api/v1/beacons`
- `POST /api/v1/auth/password`

**Features:** [F0003](../features/0003-operator-authentication.md), [F0004](../features/0004-fastapi-backend-foundation.md)

## Xero C2 Backend

FastAPI C2 service running with `XERO_SERVICE_ROLE=c2`. It can run locally or remotely and is connected from the UI Settings page.

**Current responsibilities:** C2 connection password validation, C2 session token issuance/validation, authenticated C2-only `/ws/operator` realtime fan-out, Redis `events:operator` subscription, C2-role beacon registration/listing with opaque token hash persistence, token-authenticated beacon heartbeat, stale/offline state transitions, and `beacon_events` audit persistence.

**Default embedded responsibilities:** The C2 backend is the default embedded beacon handler and embedded scanner. External handler and scanner workers are optional planned extensions, not prerequisites for local or single-server use.

**Current public interfaces:**

- `POST /api/v1/c2/connect`
- `GET /api/v1/c2/session`
- `GET /ws/operator`
- `POST /api/v1/beacons/register`
- `GET /api/v1/beacons`
- `GET /api/v1/beacons/{beacon_id}`
- `POST /api/v1/beacons/{beacon_id}/heartbeat`
- `GET /health`
- `GET /ready`

**Future responsibilities:** Encrypted binary protocol key exchange, task dispatch, result storage, embedded scanner execution, scanner worker orchestration, module orchestration, handler routing, handler pool assignment, and failover events.

**Features:** [F0004](../features/0004-fastapi-backend-foundation.md), [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md), [F0014](../features/0014-task-queue.md), [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Connection Handlers

Lightweight Go relays accepting beacon traffic and forwarding it to Xero C2 through an encrypted tunnel. The C2 backend remains the embedded handler default; external handlers are optional dedicated nodes for distribution, fault tolerance, traffic separation, and load-balanced beacon connection management.

**Responsibilities:** TLS termination for beacons, tunnel to C2 backend, traffic masking, handler registration/heartbeat, connection counts, capacity reporting, and graceful draining. Handler pools later assign beacons to healthy handlers and migrate beacons when a handler goes offline.

**Features:** [F0038](../features/0038-connection-handler-binary.md)-[F0040](../features/0040-handler-traffic-masking.md), [F0109](../features/0109-handler-load-balancing.md)

## Scanner Workers

Scanner workers execute recon jobs under C2 control. The C2 backend provides the embedded scanner default; external scanners are planned dedicated nodes for remote vantage points, larger scan workloads, and distributed scan sharding.

**Responsibilities:** Scanner registration/heartbeat, capability reporting, job assignment, progress updates, result submission, and controlled shutdown/draining. Distributed scan orchestration splits one scan into shards and merges results into one operator-visible result set.

**Features:** [F0022](../features/0022-port-scanning-module.md), [F0023](../features/0023-service-enumeration-module.md), [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Beacon Pivot Workers / Proxies

Later pivot mode allows an installed beacon to act as a scoped scanner or proxy from its network vantage point. Pivot operations must remain explicitly tied to project scope and operator authorization.

**Responsibilities:** Execute approved pivot scan jobs, proxy approved connections, report progress/results to C2, and preserve audit metadata for every pivot route.

**Features:** [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)

## Beacons (Agents)

Payloads on authorized target systems. MVP implementation is Go; Rust/C#/C++ are planned for v2.

**Responsibilities:** Register, heartbeat, execute tasks, maintain sessions, and apply profiles.

**Features:** [F0015](../features/0015-go-beacon-agent.md), [F0021](../features/0021-traffic-shaping-profiles.md)

## Data Stores

| Store | Role | Feature |
| :--- | :--- | :--- |
| PostgreSQL | Persistence foundation, users, beacon registration metadata, hashed opaque beacon token material, heartbeat profile fields, and beacon status events; task/session/asset/handler/scanner/plugin records land in dependent features | [F0005](../features/0005-postgresql-persistence.md), [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| Redis | Readiness plus queue, pub/sub, cache, and rate-limit foundations; F0008 uses `events:operator` for operator realtime; later handler/scanner health and work distribution use owned dependent feature specs | [F0006](../features/0006-redis-message-bus.md), [F0008](../features/0008-operator-websocket-realtime.md) |
