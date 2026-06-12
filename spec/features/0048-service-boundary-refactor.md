# F0048: Service Boundary Refactor

**Status:** Complete
**Priority:** P0
**Dependencies:** F0001-F0010

## Summary

Split the previous role-switched backend into separate deployable services: local BFF API, C2 API, beacon handler scaffold, scanner scaffold, and shared common Python primitives. This feature establishes service boundaries and infrastructure only; binary protocol, handler tunnel, scanner registry, distributed scanning, tasking, and pivot behavior remain owned by later features.

## Implementation Notes

- BFF code lives under `platform/services/bff-api/` and owns bootstrap authentication, bootstrap user persistence, protected local health/readiness, `/api/v1/me`, and password changes (bootstrap scope only after F0074).
- C2 code lives under `platform/services/c2-api/` and owns C2 connection/session, operator realtime WebSocket, beacon registration/list/detail, beacon heartbeat, stale/offline monitor, beacon event persistence, and C2 persistence.
- Beacon handler and scanner code live under `platform/services/beacon-handler/` and `platform/services/scanner/` as runnable health/readiness scaffolds.
- Shared Python primitives live under `platform/common/python/xero_common/`.
- BFF and C2 use separate Alembic roots and version tables.
- Separate OpenAPI specs are generated for BFF, C2, beacon handler, and scanner APIs.

## Stage Acceptance Criteria

### Stage 1: Code and route boundaries

- [x] BFF and C2 use separate package directories.
- [x] Common reusable code is moved to `xero_common`.
- [x] BFF does not mount C2 routes.
- [x] C2 does not mount BFF login or operator password routes.
- [x] BFF no longer owns `/api/v1/beacons`.

### Stage 2: Persistence boundaries

- [x] BFF Alembic root owns `users`.
- [x] C2 Alembic root owns `beacons` and `beacon_events`.
- [x] Fresh SQLite migration tests prove each service creates only its owned tables.
- [x] Existing local Docker volumes are not migrated automatically.

### Stage 3: Infrastructure boundaries

- [x] `docker-compose.bff.yml` defines the local UI/BFF stack.
- [x] `docker-compose.c2.yml` defines the C2 stack.
- [x] `docker-compose.handler.yml` defines the beacon handler scaffold.
- [x] `docker-compose.scanner.yml` defines the scanner scaffold.
- [x] `docker-compose.yml` remains as a temporary BFF compatibility alias.

### Stage 4: API documentation boundaries

- [x] `platform/docs/api/bff.openapi.yaml` is generated and tracked.
- [x] `platform/docs/api/c2.openapi.yaml` is generated and tracked.
- [x] `platform/docs/api/beacon-handler.openapi.yaml` is generated and tracked.
- [x] `platform/docs/api/scanner.openapi.yaml` is generated and tracked.
- [x] `scripts/openapi.py check all` validates all service specs.

## Test Plan

- [x] Unit tests prove service route ownership and no leaked BFF/C2 paths.
- [x] Unit tests cover BFF auth and password change.
- [x] Unit tests cover C2 connect/session, registration, heartbeat, stale/offline transition, and status filtering.
- [x] Unit tests cover split Alembic migration roots.
- [x] Compose contract tests cover all four compose files.
- [x] Behave scenarios cover BFF-only and C2-only route ownership.
- [x] OpenAPI drift checks cover all API services.
- [x] Frontend lint, unit tests, and build pass after removing stale BFF beacon helper.

## Out Of Scope

- Handler binary/tunnel behavior. See [F0038](0038-connection-handler-binary.md) and [F0039](0039-handler-tunnel-to-core.md).
- Worker pairing, heartbeat, and local scaffold provisioning. See [F0049](0049-c2-infrastructure-worker-pairing.md).
- Scanner job assignment and execution. See [F0045](0045-scanner-worker-registry.md).
- Distributed scanning. See [F0046](0046-distributed-scan-orchestration.md).
- Beacon pivot scanning/proxying. See [F0047](0047-beacon-pivot-scanning-and-proxying.md).
- Beacon binary protocol and task queues. See [F0011](0011-beacon-binary-protocol.md) and [F0014](0014-task-queue.md).

## Follow-up (F0074)

- C2 Alembic root gains `operators`; BFF `users` remains bootstrap-only.
- C2 owns operator auth routes; BFF auth routes are scoped to bootstrap setup.
- Remove `POST /api/v1/c2/connect` from C2; operator JWT replaces anonymous connect tokens.
