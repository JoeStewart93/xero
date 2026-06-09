# Data Model

## PostgreSQL Entities

| Entity | Purpose | Feature |
| :--- | :--- | :--- |
| `users` | Operator and local admin accounts with BCrypt hashes, roles, enabled flag, and timestamps | [F0003](../features/0003-operator-authentication.md) |
| `beacons` | Registration metadata, last seen, status, opaque token hash, heartbeat sleep/jitter profile defaults, and stale/offline state | [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| `beacon_events` | Beacon status transition audit log for stale offline and heartbeat recovery events | [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| `tasks` | Command/module jobs dispatched to beacons | [F0014](../features/0014-task-queue.md) |
| `task_results` | Output and status from completed tasks | [F0017](../features/0017-result-collection.md) |
| `sessions` | Interactive shell/file/registry sessions | [F0018](../features/0018-interactive-shell-session.md) |
| `assets` | Inventory records linked to beacons and discovered hosts | [F0030](../features/0030-asset-inventory.md) |
| `asset_groups` | Manual and automatic groupings | [F0031](../features/0031-automatic-asset-grouping.md) |
| `handlers` | Registered external connection handler instances with status, capacity, connected beacons, heartbeat, and tunnel metadata | [F0038](../features/0038-connection-handler-binary.md), [F0039](../features/0039-handler-tunnel-to-core.md) |
| `handler_pools` | Handler assignment policy, health scores, weights, and failover configuration | [F0109](../features/0109-handler-load-balancing.md) |
| `scanner_workers` | Embedded C2 scanner record plus registered external scanner workers with status, heartbeat, capabilities, and capacity | [F0045](../features/0045-scanner-worker-registry.md) |
| `scan_jobs` | Recon scan requests, selected execution target, project scope, status, progress, and merged result summary | [F0022](../features/0022-port-scanning-module.md), [F0046](../features/0046-distributed-scan-orchestration.md) |
| `scan_shards` | Distributed scan work chunks assigned to scanner workers or later pivot workers | [F0046](../features/0046-distributed-scan-orchestration.md), [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |
| `pivot_routes` | Later beacon pivot scanner/proxy routes with scope, operator audit metadata, and lifecycle state | [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |
| `plugins` | Installed plugin metadata | [F0041](../features/0041-plugin-api.md) |

Current implementation includes the `users` table, the F0009/F0010 `beacons` table with SHA-256 opaque token hash storage, heartbeat profile fields, stale/offline status, the `beacon_events` audit table, and the F0005 persistence foundation: SQLAlchemy session management, Alembic migrations, pool configuration, reusable UUID/timestamp model primitives, and generic CRUD helpers. Full task, session, asset, handler, scanner, pivot, plugin, and expanded beacon transport data are introduced by their owning feature specs.

All entities use UUID primary keys, `created_at`, and `updated_at` timestamps unless noted in feature specs.

## Redis Usage

| Pattern | Key/Channel | Purpose | Feature |
| :--- | :--- | :--- | :--- |
| Readiness | n/a | Verify Redis dependency health for BFF/C2 stacks | [F0001](../features/0001-docker-compose-infrastructure.md) |
| Task queue | `queue:beacon:{id}` | Pending tasks per beacon | [F0014](../features/0014-task-queue.md) |
| Pub/sub | `events:operator` | Real-time UI updates | [F0008](../features/0008-operator-websocket-realtime.md) |
| Session cache | `session:{id}` | Active session state | F0018 |
| Handler health | `handler:{id}:heartbeat` | Planned handler liveness, capacity, and assignment health | [F0109](../features/0109-handler-load-balancing.md) |
| Scanner health | `scanner:{id}:heartbeat` | Planned scanner liveness, capability, and capacity health | [F0045](../features/0045-scanner-worker-registry.md) |
| Scan work queue | `queue:scanner:{id}` | Planned scan shard assignment per scanner worker | [F0046](../features/0046-distributed-scan-orchestration.md) |
| Rate limit | `ratelimit:{user}` | Operator API throttling | [F0006](../features/0006-redis-message-bus.md) |

F0006 provides reusable Redis queue, pub/sub, cache, and rate-limit primitives. F0008 uses the pub/sub foundation for operator WebSocket fan-out on `events:operator`; real task queue usage, handler/scanner health, scan shard assignment, and session-specific behavior are introduced by their owning dependent features.

## Migrations

Schema changes are managed via Alembic under `platform/backend/alembic/`. See [F0005](../features/0005-postgresql-persistence.md).

## v2 Extensions

- MFA enrollment tables. ([F0104](../features/0104-operator-mfa.md))
- Role/permission tables. ([F0105](../features/0105-multi-role-rbac.md))
- Marketplace plugin registry. ([F0106](../features/0106-plugin-marketplace.md))
