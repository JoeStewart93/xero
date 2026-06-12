# Data Model

## PostgreSQL Entities

| Entity | Purpose | Feature |
| :--- | :--- | :--- |
| users | BFF bootstrap accounts only (BCrypt hashes, bootstrap role, enabled flag, timestamps) | [F0003](../features/0003-operator-authentication.md), [F0074](../features/0074-c2-operator-authentication.md) |
| operators | C2 operator accounts with BCrypt hashes, roles, enabled flag, and timestamps | [F0074](../features/0074-c2-operator-authentication.md) |
| beacons | Registration metadata, last seen, status, opaque token hash, heartbeat sleep/jitter profile defaults, stale/offline state, protocol metadata, and transport mode/connection timestamps | [F0009](../features/0009-beacon-registration.md), [F0010](../features/0010-beacon-heartbeat-keepalive.md), [F0011](../features/0011-beacon-binary-protocol.md), [F0012](../features/0012-beacon-websocket-transport.md) |
| beacon_events | Beacon status transition audit log for stale offline and heartbeat recovery events | [F0010](../features/0010-beacon-heartbeat-keepalive.md) |
| tasks | Command/module jobs dispatched to beacons | [F0014](../features/0014-task-queue.md) |
| artifacts | Managed object metadata for build outputs, result bodies, file transfers, reports, payload outputs, and other durable artifacts | [F0015.01-AMD](../features/0015.01-amd-minio-artifact-storage.md) |
| beacon_builds | Go beacon build requests, status, configuration, denormalized artifact metadata, and artifact linkage | [F0015](../features/0015-go-beacon-agent.md), [F0015.01-AMD](../features/0015.01-amd-minio-artifact-storage.md) |
| task_results | Output and status from completed tasks | [F0017](../features/0017-result-collection.md) |
| sessions | Interactive shell/file/registry sessions | [F0018](../features/0018-interactive-shell-session.md) |
| assets | Inventory records linked to beacons and discovered hosts | [F0030](../features/0030-asset-inventory.md) |
| asset_groups | Manual and automatic groupings | [F0031](../features/0031-automatic-asset-grouping.md) |
| infrastructure_workers | C2-owned embedded, external, and C2-managed handler/scanner worker identities with status, endpoint, capabilities, capacity, current load, heartbeat, version, managed compose metadata, and last error | [F0049](../features/0049-c2-infrastructure-worker-pairing.md) |
| worker_pairing_tokens | One-time handler/scanner pairing token hashes, expiration, use timestamp, and optional pre-bound worker ID | [F0049](../features/0049-c2-infrastructure-worker-pairing.md) |
| worker_events | Worker audit events for pairing, registration, heartbeat status transitions, launch, stop, stale/offline, and provisioning failures | [F0049](../features/0049-c2-infrastructure-worker-pairing.md) |
| protocol_security_events | Redacted binary-frame validation failures such as HMAC mismatch, replay, malformed frames, unsupported versions, and decrypt failures | [F0011](../features/0011-beacon-binary-protocol.md) |
| protocol_frame_receipts | Non-sensitive protocol frame receipts with message type, session/nonce, payload digest, payload size, and optional beacon linkage | [F0011](../features/0011-beacon-binary-protocol.md) |
| handlers | Planned tunnel-specific handler metadata such as connected beacons, connected_at, drain state, certificate pinning, and relay state; identity/heartbeat lives in infrastructure_workers | [F0038](../features/0038-connection-handler-binary.md), [F0039](../features/0039-handler-tunnel-to-core.md) |
| handler_pools | Handler assignment policy, health scores, weights, and failover configuration | [F0109](../features/0109-handler-load-balancing.md) |
| scanner_workers | Planned scanner execution/assignment metadata; shared scanner identity, heartbeat, capabilities, and capacity live in infrastructure_workers | [F0045](../features/0045-scanner-worker-registry.md) |
| scan_jobs | Recon scan requests, selected execution target, project scope, status, progress, and merged result summary | [F0022](../features/0022-port-scanning-module.md), [F0046](../features/0046-distributed-scan-orchestration.md) |
| scan_shards | Distributed scan work chunks assigned to scanner workers or later pivot workers | [F0046](../features/0046-distributed-scan-orchestration.md), [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |
| pivot_routes | Later beacon pivot scanner/proxy routes with scope, operator audit metadata, and lifecycle state | [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |
| plugins | Installed plugin metadata | [F0041](../features/0041-plugin-api.md) |
| exploits | Normalized exploit records with CVE metadata, affected services, references, source attribution | [F0080](../features/0080-exploit-management-system.md) |
| exploit_sources | Exploit source configuration (Metasploit, ExploitDB, custom) with sync metadata | [F0083](../features/0083-exploit-source-adapters.md) |
| payloads | Generated payload records with language, template, encoder chain, output metadata | [F0081](../features/0081-payload-generation-system.md) |
| encoder_configs | Encoder/obfuscator configuration templates and transformation chains | [F0081](../features/0081-payload-generation-system.md) |
| post_exploit_modules | Post-exploitation module registry with execution metadata | [F0082](../features/0082-post-exploitation-orchestration.md) |
| exploit_executions | Exploit execution history with results, payload bindings, asset correlations | [F0080](../features/0080-exploit-management-system.md) |
| rootkit_configs | Saved rootkit configuration templates with platform, type, hiding/protection settings | [F0200](../features/0200-rootkit-suite-overview.md) |
| rootkit_payloads | Compiled rootkit payload binaries and metadata including target kernel version, architecture, artifact URL | [F0200](../features/0200-rootkit-suite-overview.md) |
| rootkit_instances | Active rootkit instances per beacon with status, type, configuration reference, and persistence state | [F0200](../features/0200-rootkit-suite-overview.md) |
| rootkit_build_jobs | Build server job tracking with target specs, status, progress, logs, and artifact URL | [F0207](../features/0207-rootkit-build-server.md) |
| rootkit_events | Rootkit activity audit log including activation, deactivation, heartbeat, stealth mode changes | [F0200](../features/0200-rootkit-suite-overview.md) |

Current implementation includes the BFF-owned `users` table (bootstrap accounts), the planned C2-owned `operators` table ([F0074](../features/0074-c2-operator-authentication.md)), the C2-owned F0009/F0010 beacons table with SHA-256 opaque token hash storage, heartbeat profile fields, stale/offline status, protocol version/session/public-key metadata, transport mode/connected/last-seen metadata, the C2-owned beacon_events audit table, F0011 protocol_security_events and protocol_frame_receipts, F0014 tasks, F0015 beacon_builds, F0015.01 artifacts, F0049 infrastructure_workers, worker_pairing_tokens, and worker_events, and the F0005/F0048 persistence foundation: SQLAlchemy session management, service-specific Alembic migrations, pool configuration, reusable UUID/timestamp model primitives, and generic CRUD helpers.

All entities use UUID primary keys, created_at, and updated_at timestamps unless noted in feature specs.

## Redis Usage

| Pattern | Key/Channel | Purpose | Feature |
| :--- | :--- | :--- | :--- |
| Readiness | n/a | Verify Redis dependency health for BFF/C2 stacks | [F0001](../features/0001-docker-compose-infrastructure.md) |
| Task queue | queue:beacon:{id}:{priority} | Pending task IDs per beacon and priority | [F0014](../features/0014-task-queue.md) |
| Pub/sub | events:operator | Real-time UI updates | [F0008](../features/0008-operator-websocket-realtime.md) |
| Session cache | session:{id} | Active session state | F0018 |
| Handler health | handler:{id}:heartbeat | Planned handler liveness, capacity, and assignment health | [F0109](../features/0109-handler-load-balancing.md) |
| Scanner health | scanner:{id}:heartbeat | Planned scanner liveness, capability, and capacity health | [F0045](../features/0045-scanner-worker-registry.md) |
| Scan work queue | queue:scanner:{id} | Planned scan shard assignment per scanner worker | [F0046](../features/0046-distributed-scan-orchestration.md) |
| Rate limit | ratelimit:{user} | Operator API throttling | [F0006](../features/0006-redis-message-bus.md) |
| Build queue | queue:rootkit:build | Rootkit build job queue | [F0207](../features/0207-rootkit-build-server.md) |
| Rootkit heartbeat | rootkit:{id}:heartbeat | Rootkit instance heartbeat tracking | [F0205](../features/0205-rootkit-communication.md) |
| Exploit cache | cache:exploits:{source} | Cached exploit catalog from external sources | [F0083](../features/0083-exploit-source-adapters.md) |
| Payload cache | cache:payloads:{hash} | Generated payload binary cache | [F0081](../features/0081-payload-generation-system.md) |

F0006 provides reusable Redis queue, pub/sub, cache, and rate-limit primitives. F0008 uses the pub/sub foundation for operator WebSocket fan-out on events:operator. F0014 uses per-beacon priority lists for pending task IDs; handler/scanner health, scan shard assignment, and session-specific behavior are introduced by their owning dependent features. F0207 uses Redis queue for build job distribution; F0205 uses Redis for rootkit heartbeat tracking. F0083 uses Redis for caching external exploit source data; F0081 uses Redis for caching generated payloads.

## Migrations

Schema changes are managed by service-specific Alembic roots:

| Service | Alembic root | Version table | Current ownership |
| :--- | :--- | :--- | :--- |
| BFF API | platform/services/bff-api/alembic/ | bff_alembic_version | users (bootstrap) |
| C2 API | platform/services/c2-api/alembic/ | c2_alembic_version | operators ([F0074](../features/0074-c2-operator-authentication.md)), beacons, beacon_events, tasks, beacon_builds, artifacts, infrastructure_workers, worker_pairing_tokens, worker_events, protocol_security_events, protocol_frame_receipts, exploits, exploit_sources, payloads, encoder_configs, post_exploit_modules, exploit_executions, rootkit_configs, rootkit_payloads, rootkit_instances, rootkit_build_jobs, rootkit_events |

Common SQLAlchemy helpers live under platform/common/python/xero_common/. See [F0005](../features/0005-postgresql-persistence.md) and [F0048](../features/0048-service-boundary-refactor.md).

## Object Storage

Local Docker C2 uses MinIO as an S3-compatible artifact backend. C2 stores object metadata in `artifacts` and object bytes in the configured bucket/prefix, defaulting to `xero-artifacts` and `c2`. Operators download artifacts through authenticated C2 endpoints; direct object-store credentials and presigned URLs are not exposed by the F0015.01 amendment.

## v2 Extensions

- MFA enrollment tables. ([F0104](../features/0104-operator-mfa.md))
- Role/permission tables. ([F0105](../features/0105-multi-role-rbac.md))
- Marketplace plugin registry. ([F0106](../features/0106-plugin-marketplace.md))
- Rootkit suite tables. ([F0200](../features/0200-rootkit-suite-overview.md)-[F0207](../features/0207-rootkit-build-server.md))
