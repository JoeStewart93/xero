# Xero: Modular Command & Control Platform
**Version:** 1.5.0
**Date:** June 09, 2026
**Status:** Approved
**Prepared For:** Development Team
**Changelog:** Split local BFF, C2 API, beacon handler scaffold, and scanner scaffold into separate service directories, compose files, and OpenAPI documents; added shared handler/scanner worker pairing and Settings > Infrastructure inventory.

---

## 1. Executive Overview

**Xero** is a modular Command & Control (C2) platform for authorized cybersecurity research, defensive testing, and scoped red-team operations. It automates scanning, enumeration, exploitation support, and post-exploitation workflows while keeping operator UI, local BFF services, C2 backend logic, embedded infrastructure roles, external handlers, external scanners, pivot routes, and beacons logically separated.

The current implementation has separate deployable API services:

1. **Local UI/BFF:** Serves bootstrap auth, protected BFF health, and C2 URL configuration for the frontend.
2. **C2 Backend:** Runs C2-facing services separately so it can be hosted locally or remotely. Owns C2 operator authentication, operator realtime WebSocket, completed beacon registration/heartbeat, embedded handler/scanner defaults, and shared infrastructure worker pairing/liveness control plane.
3. **Beacon Handler Scaffold:** Separate service home for future external handler work; currently health/readiness plus optional C2 worker pairing/heartbeat.
4. **Scanner Scaffold:** Separate service home for future scanner worker work; currently health/readiness plus optional C2 worker pairing/heartbeat.

Product code lives under `platform/` in the `xero` repository. Specifications live at `spec/`. See [mvp-requirements.md](mvp-requirements.md), [features/README.md](features/README.md), and [architecture/README.md](architecture/README.md).

---

## 2. System Architecture

### 2.1 Core Components

1. **Xero UI:** React + TypeScript operator console served by the local frontend container.
2. **Xero BFF:** Local FastAPI service that owns bootstrap login, protected UI health endpoints, and C2 URL configuration.
3. **Xero C2 Backend:** FastAPI service under `platform/services/c2-api/`; it owns C2 operator authentication, hosts the operator realtime WebSocket, owns completed beacon registration/heartbeat, provides embedded handler/scanner defaults, and owns the shared infrastructure worker pairing/liveness control plane.
4. **External Beacon Handlers:** Lightweight relays that pair/heartbeat with Xero C2 today and later accept beacon traffic/tunnel it to C2 for distributed connection management, fault tolerance, load balancing, and traffic separation.
5. **External Scanner Workers:** Scanner nodes that pair/heartbeat with C2 today and later execute recon jobs or scan shards and return progress/results for aggregation.
6. **Beacon Pivot Workers / Proxies:** Later capability where an installed beacon acts as a scoped scanner or proxy from its network vantage point.
7. **Beacons (Agents):** Payloads deployed on authorized target systems. They communicate directly with the embedded C2 handler by default or through external/ad-hoc handlers in later phases.

### 2.2 Current Operator Flow

```text
[ Operator Browser ]
        |
        v
[ Xero UI ] -> [ Local Xero BFF ] -> [ Local Postgres / Redis ]
        |
        | C2 connection configured in Settings
        v
[ Xero C2 Backend ] -> [ C2 Postgres / Redis ]
```

The UI uses a dual auth model ([F0074](features/0074-c2-operator-authentication.md)):

- **Bootstrap:** When no C2 URL is configured, the UI authenticates to the BFF using `POST /auth/login` (bootstrap admin) to configure the C2 backend URL and access BFF health.
- **Operational:** When a C2 URL is configured, login authenticates to C2 using `POST /api/v1/auth/login` and stores an operator JWT used for all C2 API calls and `/ws/operator`.

When authenticated to C2, the UI opens `/ws/operator` directly on the C2 backend with the operator JWT. C2 publishes operator-visible events through Redis channel `events:operator`.

### 2.3 Beacon Network Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded handler | Beacon -> TLS/WebSocket -> Xero C2 Backend embedded handler -> operator `/ws/operator` -> Xero UI | P0 |
| External handler | Beacon -> external connection handler -> Xero C2 Backend -> operator `/ws/operator` -> Xero UI | P1 |
| Handler pool | Beacon -> assigned healthy handler -> Xero C2 Backend; beacons migrate when a handler fails | P1 |
| Ad-hoc handler | Beacon A -> Beacon B acting as handler -> Xero C2 Backend -> operator `/ws/operator` -> Xero UI | P2 |

### 2.4 Scanner Execution Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded scanner | Xero UI -> C2 Backend embedded scanner -> result aggregation -> Xero UI | P0 |
| Selected scanner | Xero UI -> C2 Backend -> selected external scanner worker -> result aggregation -> Xero UI | P1 |
| Distributed scanner pool | Xero UI -> C2 Backend -> multiple scanner workers process shards -> merged results -> Xero UI | P1 |
| Beacon pivot | Xero UI -> C2 Backend -> authorized beacon pivot worker/proxy -> scoped scan/proxy result -> Xero UI | P2 |

---

## 3. Product Requirements Document (PRD)

### 3.1 Product Goals

- **Modularity:** Allow operators to swap profiles and infrastructure roles without redeploying the entire platform.
- **Scalability:** Support many beacons and recon jobs through C2 embedded defaults first, then external handler and scanner fleets.
- **Stealth:** Minimize network noise through traffic shaping, encryption, and separated infrastructure.
- **Resilience:** Maintain operations if primary C2 endpoints, handlers, or scanners rotate or fail.

### 3.2 Scope

- **In Scope (MVP):** See [features/README.md](features/README.md) F0001-F0047 plus promoted handler pool/failover work.
- **Out of Scope (MVP):** See [features/README.md](features/README.md) remaining v2 items F0101-F0110, excluding promoted F0109.

### 3.3 User Personas

- **Operator:** Uses the UI to manage project scope, recon, beacons, tasking, assets, and reporting.
- **Local Administrator:** Uses the BFF bootstrap admin account to configure the C2 backend URL and access BFF health. Does not receive operational C2 authority without a C2 operator account.
- **Infrastructure Admin:** Manages C2 servers, handlers, scanner workers, and later pivot routes. Expanded RBAC is v2 (F0105).
- **Developer:** Extends the platform via plugins and modules.

---

## 4. Functional Requirements

### 4.0 General

- **GR-01:** Must be deployable via Docker Compose. ([F0001](features/0001-docker-compose-infrastructure.md))

### 4.1 Local UI/BFF

- **FR-01:** Python FastAPI BFF foundation with health, readiness, CORS, OpenAPI, and protected operator endpoints. ([F0004](features/0004-fastapi-backend-foundation.md))
- **FR-02:** Bootstrap username/password authentication with BCrypt-hashed BFF users and JWT sessions for setup scope. ([F0003](features/0003-operator-authentication.md))
- **FR-03:** C2 operator username/password authentication with BCrypt-hashed C2 operators and operator JWT sessions. ([F0074](features/0074-c2-operator-authentication.md))
- **FR-04:** Protected BFF operator API routes include `/api/v1/health`, `/api/v1/ready`, `/api/v1/me`, and `/api/v1/auth/password`.

### 4.2 Xero C2 Backend

- **FR-05:** Python FastAPI C2 service role for operator realtime, beacon state, task queues, encryption keys, embedded handler/scanner defaults, handler routing, scanner orchestration, and future module orchestration. ([F0004](features/0004-fastapi-backend-foundation.md), [F0008](features/0008-operator-websocket-realtime.md))
- **FR-06:** WebSocket and HTTP long-polling for beacons. ([F0012](features/0012-beacon-websocket-transport.md), [F0013](features/0013-beacon-http-longpoll-fallback.md))
- **FR-07:** PostgreSQL for beacons, sessions, task history, users, and future persistent entities. ([F0005](features/0005-postgresql-persistence.md))
- **FR-08:** Redis for task queues, pub/sub, cache, and rate limiting. ([F0006](features/0006-redis-message-bus.md))

### 4.3 Management UI

- **FR-09:** React + TypeScript + Tailwind UI with Stitch-first UI development. ([F0007](features/0007-react-ui-shell.md))
- **FR-10:** Current protected routes include `/home`, `/projects`, `/recon`, `/beacons`, `/exploits`, `/payloads`, `/assets`, `/reports`, `/loot`, `/settings`, and `/health`; several later-feature routes currently render shell stubs only.
- **FR-11:** Current side navigation: Home, Projects, Recon, Beacons, Exploits, Payloads, Assets, Reports, Loot, Settings, and separated utility Health/Realtime.
- **FR-12:** Project scope leads into Recon workflows; C2-dependent workflows remain locked until a C2 backend connection is configured.

### 4.4 Connection Handlers

- **FR-13:** C2 backend provides the embedded/default beacon handler for direct beacon connectivity.
- **FR-14:** Standalone external handler binaries for Linux/Windows. ([F0038](features/0038-connection-handler-binary.md))
- **FR-15:** Encrypted handler tunnel to Xero C2. ([F0039](features/0039-handler-tunnel-to-core.md))
- **FR-16:** Handler pools support health, assignment, failover, and beacon migration. ([F0109](features/0109-handler-load-balancing.md))
- **FR-17:** Ad-hoc handler installation on beacons. ([F0044](features/0044-adhoc-handler-installation.md))
- **FR-18:** Traffic masking. ([F0040](features/0040-handler-traffic-masking.md))
- **FR-18a:** Handler/scanner worker pairing, heartbeat, inventory, and local scaffold provisioning. ([F0049](features/0049-c2-infrastructure-worker-pairing.md))

### 4.5 Scanners and Recon

- **FR-19:** C2 backend provides the embedded/default scanner for recon workflows.
- **FR-20:** External scanner workers can pair/register with C2 and report health/capabilities through F0049; scanner job execution remains with F0045. ([F0049](features/0049-c2-infrastructure-worker-pairing.md), [F0045](features/0045-scanner-worker-registry.md))
- **FR-21:** Scan orchestration can select one scanner or distribute a single scan across multiple scanner workers, then merge results. ([F0046](features/0046-distributed-scan-orchestration.md))
- **FR-22:** Later pivot mode allows an installed beacon to scan/proxy from its network vantage point within explicit project scope. ([F0047](features/0047-beacon-pivot-scanning-and-proxying.md))

### 4.6 Exploits and Payloads

- **FR-23:** Exploit management system with multi-source aggregation (Metasploit, ExploitDB, built-in). ([F0080](features/0080-exploit-management-system.md), [F0083](features/0083-exploit-source-adapters.md))
- **FR-24:** Exploit suggestion engine based on asset and service enumeration profiles. ([F0080](features/0080-exploit-management-system.md))
- **FR-25:** Multi-language payload generation system (Go, Python, PowerShell, Bash, Rust, C#). ([F0081](features/0081-payload-generation-system.md))
- **FR-26:** Encoder/obfuscator pipeline with configurable transformation chains. ([F0081](features/0081-payload-generation-system.md))
- **FR-27:** Post-exploitation orchestration with chained execution workflows. ([F0082](features/0082-post-exploitation-orchestration.md))
- **FR-28:** Unified payload-to-beacon deployment integration. ([F0081](features/0081-payload-generation-system.md))

### 4.7 Beacons (Agents)

- **FR-29:** Process injection and token impersonation are v2. ([F0101](features/0101-process-injection-token-impersonation.md))
- **FR-30:** Mutual TLS (mTLS) when connecting to handlers.
- **FR-31:** Custom profiles for jitter, sleep, user agents, and traffic shaping. ([F0021](features/0021-traffic-shaping-profiles.md))

---

## 5. Technical Requirements

See [architecture/](architecture/README.md) for the detailed architecture reference.

| Component | Technology |
| :--- | :--- |
| Local BFF | Python (FastAPI) |
| C2 Backend | Python (FastAPI) |
| Database | PostgreSQL |
| Message Bus | Redis (MVP); RabbitMQ v2 ([F0110](features/0110-rabbitmq-message-bus.md)) |
| Management UI | React + TypeScript + Tailwind |
| Handlers | Go (MVP) |
| Scanner Workers | Python or Go planned; embedded scanner begins in C2 backend |
| Beacons | Go (MVP); Rust, C#, C++ v2 ([F0107](features/0107-additional-beacon-languages.md)) |

---

## 6. Security Requirements

See [architecture/security-model.md](architecture/security-model.md).

- **SR-01:** Encrypted in transit.
- **SR-02:** Secrets via environment variables or Vault.
- **SR-03:** Handler certificate pinning.
- **SR-04:** Traffic shaping. ([F0021](features/0021-traffic-shaping-profiles.md))
- **SR-05:** Non-development deployments must override default JWT, bootstrap admin, and C2 admin seed credentials.
- **SR-06:** Scanner and pivot execution must remain constrained to active project scope and preserve audit metadata.

---

## 7. Deployment Strategy

The local UI/BFF stack is started with `docker compose -f docker-compose.bff.yml up --build` from `platform/`. `docker-compose.yml` remains a temporary BFF alias. The optional local C2 backend stack is started with `docker compose -f docker-compose.c2.yml up --build`. Handler and scanner scaffolds are started with `docker-compose.handler.yml` and `docker-compose.scanner.yml` or launched from `Settings > Infrastructure` when local provisioning is enabled. Handler tunnel behavior and scanner execution are planned follow-up work; the C2 backend remains the default embedded handler/scanner when external workers are absent.

Follow numbered features in [features/README.md](features/README.md). Summary aligns with MVP phases in [mvp-requirements.md](mvp-requirements.md#6-implementation-phases).

---

## 8. Appendix: Data Flow Diagram

```text
[ Operator ]
    |
[ Xero UI ]
    |
    | REST + JWT
[ Local Xero BFF ] <----> [ BFF PostgreSQL ]
    |                       [ BFF Redis ]
    |
    | C2 operator JWT from /api/v1/auth/login
    v
[ Xero C2 Backend ] <----> [ C2 PostgreSQL ]
    |                       [ C2 Redis ]
    |
    | Embedded handler path, default
[ Beacon 1 ]

    | P1 external handler path
[ Connection Handler A ] -- F0049 pairing/heartbeat --> [ Xero C2 Backend ]
    |
[ Beacon 2 ]

    | Embedded scanner path, default
[ Recon Target ]

    | P1 external scanner path
[ Scanner Worker A ] -- F0049 pairing/heartbeat --> [ Xero C2 Backend ]
[ Scanner Worker A ] ---> [ Recon Target ] (scan execution planned)

    | P2 pivot scanner/proxy path
[ Beacon Pivot ] ----> [ Internal Recon/Proxy Target ]
```

---

## 9. Post-MVP Capabilities (v2+)

Documented as remaining v2 features F0101-F0110, excluding promoted F0109. See [features/README.md](features/README.md#post-mvp-v2).

---

## 10. Authorized Use

Xero is intended for **authorized cybersecurity research, defensive security testing, and red-team operations** with explicit written permission from system owners.

See [mvp-requirements.md](mvp-requirements.md#10-authorized-use) and [architecture/security-model.md](architecture/security-model.md).
