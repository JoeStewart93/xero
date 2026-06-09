# System Overview

**Xero** is a modular Command & Control (C2) platform for authorized cybersecurity research, defensive testing, and scoped red-team operations.

## Vision

Xero automates scanning, enumeration, and post-exploitation workflows through a decoupled architecture. The operator UI, local BFF, C2 backend, embedded infrastructure roles, external handler/scanner fleets, and beacons are logically separate so the operator console can run locally while C2 logic runs locally or remotely.

## Product Goals

- **Modularity:** Swap communication profiles and infrastructure roles without redeploying the full platform.
- **Scalability:** Scale to many beacons and recon jobs through embedded C2 defaults first, then external handler and scanner fleets.
- **Stealth:** Traffic shaping and encryption minimize network noise.
- **Resilience:** Handler nodes, scanner nodes, pivot routes, and remote C2 deployments maintain operations when individual endpoints fail.

## Current Service Roles

| Role | Current responsibility | Compose stack |
| :--- | :--- | :--- |
| Xero UI | Operator web console | `docker-compose.yml` |
| Local Xero BFF | Operator auth, protected health, C2 connection setup | `docker-compose.yml` |
| Xero C2 Backend | C2 connection auth, operator realtime, completed beacon registration, completed heartbeat/offline state, embedded beacon handler default, embedded scanner default, and future tasking APIs | `docker-compose.c2.yml` |
| PostgreSQL / Redis | Per-stack persistence, readiness, C2 operator events, and future queues/cache | Both stacks |
| External beacon handlers | Planned dedicated beacon connection nodes that tunnel to C2 | Planned external deployment |
| External scanner workers | Planned dedicated recon workers registered to C2 | Planned external deployment |
| Beacon pivot workers/proxies | Later beacon-hosted scan/proxy vantage points inside authorized scope | Planned pivot deployment |

## Current Operator Flow

```text
Operator Browser
  -> Xero UI
  -> Local Xero BFF
  -> Local PostgreSQL / Redis

Settings connection:
Xero UI
  -> POST /api/v1/c2/connect on Xero C2 Backend
  -> C2 token stored in the browser connection context

Operator realtime:
Xero UI
  -> ws(s)://<c2-backend>/ws/operator with C2 bearer token
  -> Xero C2 Backend subscribes to Redis events:operator
```

## Beacon Network Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded handler | Beacon -> TLS/WebSocket -> Xero C2 Backend embedded handler -> operator `/ws/operator` -> Xero UI | P0 |
| External handler | Beacon -> external handler -> Xero C2 Backend -> operator `/ws/operator` -> Xero UI | P1 |
| Handler pool | Beacon -> assigned healthy handler -> Xero C2 Backend; beacons migrate when a handler fails | P1 |
| Ad-hoc handler | Beacon A -> Beacon B acting as handler -> Xero C2 Backend -> operator `/ws/operator` -> Xero UI | P2 |

## Scanner Execution Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded scanner | Xero UI -> C2 Backend embedded scanner -> result aggregation -> Xero UI | P0 |
| Selected scanner | Xero UI -> C2 Backend -> selected external scanner worker -> result aggregation -> Xero UI | P1 |
| Distributed scanner pool | Xero UI -> C2 Backend -> multiple scanner workers process shards -> merged results -> Xero UI | P1 |
| Beacon pivot | Xero UI -> C2 Backend -> authorized beacon pivot worker/proxy -> scoped scan or proxy result -> Xero UI | P2 |

## Related Features

- Foundation and operator realtime: [F0001](../features/0001-docker-compose-infrastructure.md)-[F0008](../features/0008-operator-websocket-realtime.md)
- Core C2: [F0009](../features/0009-beacon-registration.md)-[F0015](../features/0015-go-beacon-agent.md)
- Handlers: [F0038](../features/0038-connection-handler-binary.md)-[F0044](../features/0044-adhoc-handler-installation.md), [F0109](../features/0109-handler-load-balancing.md)
- Scanner workers and distributed recon: [F0045](../features/0045-scanner-worker-registry.md)-[F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)

See [overview.md](../overview.md) for the full PRD.
