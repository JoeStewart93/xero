# Components

## Xero UI

React + TypeScript + Tailwind web dashboard for operators. It is served by the frontend container and talks to the local BFF using `VITE_API_BASE_URL`.

**Current responsibilities:** Login screen (bootstrap and C2 operator modes), authenticated app shell, direct C2 operator realtime client/status, Home overview, Projects foundation, Recon foundation, C2-backed Beacons overview/detail route, Settings C2 URL configuration and connection status, Settings/Infrastructure worker inventory and pairing/provisioning workflow, protected Health page, and routeable shell stubs for Exploits, Payloads, Assets, Reports, and Loot. Inventory lives under Assets.

**Features:** [F0007](../features/0007-react-ui-shell.md), [F0024](../features/0024-dashboard-ui.md)-[F0028](../features/0028-module-browser-ui.md)

## Local Xero BFF

FastAPI backend-for-frontend service implemented under `platform/services/bff-api/`. It is local to the UI stack and does not own C2 beacon, realtime, tasking, handler, or scanner behavior.

**Current responsibilities:** Bootstrap login, JWT issuance for setup scope, PostgreSQL-backed bootstrap user records, default development bootstrap admin seeding, protected local health/readiness, bootstrap password change, CORS, and BFF OpenAPI generation.

**Current public interfaces:**

- `POST /auth/login`
- `GET /health`
- `GET /ready`
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/me`
- `POST /api/v1/auth/password`

**Features:** [F0003](../features/0003-operator-authentication.md), [F0004](../features/0004-fastapi-backend-foundation.md), [F0074](../features/0074-c2-operator-authentication.md) (bootstrap scope)

## Xero C2 Backend

FastAPI C2 service implemented under `platform/services/c2-api/`. It can run locally or remotely and is connected from the UI Settings page.

**Current responsibilities:** C2 operator authentication and JWT issuance, operator-scoped session validation, authenticated C2-only `/ws/operator` realtime fan-out, Redis `events:operator` subscription, C2-role beacon registration/listing with opaque token hash persistence, token-authenticated beacon heartbeat, stale/offline state transitions, `beacon_events` audit persistence, embedded handler/scanner identity seeding, infrastructure worker pairing/registration/heartbeat, worker stale detection, worker event persistence, C2 operator admin CRUD (F0074), and local scaffold launch/stop when provisioning is enabled.

**Default embedded responsibilities:** The C2 backend is the default embedded beacon handler and embedded scanner. External handler and scanner scaffold services can pair and heartbeat through the C2 worker control plane, but they are not prerequisites for local or single-server use.

**Current public interfaces:**

- `POST /api/v1/auth/login`
- `GET /api/v1/me`
- `POST /api/v1/auth/password`
- `GET /api/v1/c2/session` (operator session check; replaces connect flow)
- `GET /ws/operator`
- `POST /api/v1/beacons/register`
- `GET /api/v1/beacons`
- `GET /api/v1/beacons/{beacon_id}`
- `POST /api/v1/beacons/{beacon_id}/heartbeat`
- `GET /api/v1/infrastructure/workers`
- `POST /api/v1/infrastructure/pairing-tokens`
- `POST /api/v1/infrastructure/workers/register`
- `POST /api/v1/infrastructure/workers/{worker_id}/heartbeat`
- `POST /api/v1/infrastructure/workers/launch`
- `POST /api/v1/infrastructure/workers/{worker_id}/stop`
- `GET /health`
- `GET /ready`

**Future responsibilities:** Encrypted binary protocol key exchange, task dispatch, result storage, embedded scanner execution, scanner job orchestration, module orchestration, handler routing, handler pool assignment, and failover events.

**Features:** [F0004](../features/0004-fastapi-backend-foundation.md), [F0074](../features/0074-c2-operator-authentication.md), [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md), [F0014](../features/0014-task-queue.md), [F0049](../features/0049-c2-infrastructure-worker-pairing.md), [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Connection Handlers

Lightweight Go relays accepting beacon traffic and forwarding it to Xero C2 through an encrypted tunnel. The C2 backend remains the embedded handler default; external handlers are optional dedicated nodes for distribution, fault tolerance, traffic separation, and load-balanced beacon connection management.

**Current implementation:** Runnable scaffold under `platform/services/beacon-handler/` with `GET /health`, `GET /ready`, Dockerfile, compose file, OpenAPI spec, optional C2 pairing token registration, persisted worker session file, and C2 heartbeat loop.

**Planned responsibilities:** TLS termination for beacons, tunnel to C2 backend, traffic masking, handler registration/heartbeat, connection counts, capacity reporting, and graceful draining. Handler pools later assign beacons to healthy handlers and migrate beacons when a handler goes offline.

**Features:** [F0049](../features/0049-c2-infrastructure-worker-pairing.md), [F0038](../features/0038-connection-handler-binary.md)-[F0040](../features/0040-handler-traffic-masking.md), [F0109](../features/0109-handler-load-balancing.md)

## Scanner Workers

Scanner workers execute recon jobs under C2 control. The C2 backend provides the embedded scanner default; external scanners are planned dedicated nodes for remote vantage points, larger scan workloads, and distributed scan sharding.

**Current implementation:** Runnable scaffold under `platform/services/scanner/` with `GET /health`, `GET /ready`, Dockerfile, compose file, OpenAPI spec, optional C2 pairing token registration, persisted worker session file, and C2 heartbeat loop.

**Planned responsibilities:** Scanner registration/heartbeat, capability reporting, job assignment, progress updates, result submission, and controlled shutdown/draining. Distributed scan orchestration splits one scan into shards and merges results into one operator-visible result set.

**Features:** [F0049](../features/0049-c2-infrastructure-worker-pairing.md), [F0022](../features/0022-port-scanning-module.md), [F0023](../features/0023-service-enumeration-module.md), [F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md)

## Beacon Pivot Workers / Proxies

Later pivot mode allows an installed beacon to act as a scoped scanner or proxy from its network vantage point. Pivot operations must remain explicitly tied to project scope and operator authorization.

**Responsibilities:** Execute approved pivot scan jobs, proxy approved connections, report progress/results to C2, and preserve audit metadata for every pivot route.

**Features:** [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)

## Beacons (Agents)

Payloads on authorized target systems. MVP implementation is Go; Rust/C#/C++ are planned for v2.

**Responsibilities:** Register, heartbeat, execute tasks, maintain sessions, and apply profiles.

**Features:** [F0015](../features/0015-go-beacon-agent.md), [F0021](../features/0021-traffic-shaping-profiles.md)

## Exploit Management System

Exploit catalog, suggestion engine, and execution orchestration with multi-source aggregation.

**Responsibilities:** Aggregate exploits from Metasploit, ExploitDB, and built-in sources; normalize to unified schema; suggest exploits based on asset/service profiles; orchestrate exploit execution with payload binding; track results and correlate with assets.

**Features:** [F0080](../features/0080-exploit-management-system.md), [F0083](../features/0083-exploit-source-adapters.md)

## Payload Generation System

Multi-language payload generation with encoder/obfuscator pipeline and beacon deployment integration.

**Responsibilities:** Generate payloads in Go, Python, PowerShell, Bash, Rust, C#; apply encoder/obfuscator transformations; integrate traffic shaping profiles; provide unified beacon deployment workflow.

**Features:** [F0081](../features/0081-payload-generation-system.md)

## Post-Exploitation Orchestrator

Chained execution workflow coordinator for post-exploitation modules.

**Responsibilities:** Orchestrate chained execution (exploit → payload → post-exploit modules); manage post-exploitation module registry; coordinate credential harvesting, lateral movement, persistence; aggregate results and correlate with loot.

**Features:** [F0082](../features/0082-post-exploitation-orchestration.md)

## Data Stores

| Store | Role | Feature |
| :--- | :--- | :--- |
| PostgreSQL | Persistence foundation, BFF bootstrap users, C2 operators, beacon registration metadata, hashed opaque beacon token material, heartbeat profile fields, beacon status events, infrastructure workers, worker pairing token hashes, and worker events; task/session/asset/plugin records land in dependent features | [F0005](../features/0005-postgresql-persistence.md), [F0003](../features/0003-operator-authentication.md), [F0074](../features/0074-c2-operator-authentication.md), [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md), [F0049](../features/0049-c2-infrastructure-worker-pairing.md) |
| Redis | Readiness plus queue, pub/sub, cache, and rate-limit foundations; F0008 uses `events:operator` for operator realtime; later handler/scanner health and work distribution use owned dependent feature specs | [F0006](../features/0006-redis-message-bus.md), [F0008](../features/0008-operator-websocket-realtime.md) |

## Shared Code

Shared Python primitives live in `platform/common/python/xero_common/`. This package provides reusable database/session helpers, Redis/event helpers, readiness checks, password/JWT/token helpers, CRUD helpers, and UUID/timestamp model mixins. Service-specific settings, routes, models, schemas, migrations, and OpenAPI specs remain in each service directory.
