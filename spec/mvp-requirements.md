# Xero: MVP Requirements
**Version:** 1.3.0
**Date:** June 08, 2026
**Status:** Approved
**Parent Document:** overview.md
**Changelog:** Realigned MVP requirements with the implemented UI/BFF stack, separate C2 backend stack, local DB-backed auth, protected health UI, and current lifecycle navigation.

---

## 1. Executive Summary

This document defines the MVP scope and technical decisions for **Xero**, a modular Command & Control platform for authorized security work. Detailed implementation specs with test plans live in [features/](features/README.md).

Product code lives under `platform/`. Specifications live under `spec/`.

---

## 2. Technical Decisions

### 2.1 Platform APIs

- **Framework:** Python FastAPI for both local BFF and C2 backend service roles. ([F0004](features/0004-fastapi-backend-foundation.md))
- **Local BFF role:** `XERO_SERVICE_ROLE=bff`; owns operator auth, protected UI health, and C2 connection setup.
- **C2 backend role:** `XERO_SERVICE_ROLE=c2`; owns C2 connection authentication, operator realtime, completed beacon registration, completed heartbeat/offline state, and future tasking APIs.

### 2.2 Deployment Model

- `platform/docker-compose.yml` runs the local UI/BFF stack: frontend, backend/BFF, PostgreSQL, and Redis.
- `platform/docker-compose.c2.yml` runs a separate C2 backend stack: C2 backend, C2 PostgreSQL, and C2 Redis.
- The UI can connect to a local or remote C2 backend from Settings using `C2_CONNECT_PASSWORD`.

### 2.3 Authentication (MVP)

- Username/password + JWT for local operator access. ([F0003](features/0003-operator-authentication.md))
- BCrypt password hashes stored in PostgreSQL.
- Default development users: `operator/operator_password` and local administrator `admin/admin`.
- Default credentials and JWT/C2 secrets are rejected outside development/test modes.
- C2 backend connection uses a separate password/token flow via `/api/v1/c2/connect`.
- Single operator/admin-style role model for MVP; MFA and richer RBAC are v2. ([F0104](features/0104-operator-mfa.md), [F0105](features/0105-multi-role-rbac.md))

### 2.4 Beacon Languages

- **MVP:** Go only. ([F0015](features/0015-go-beacon-agent.md))
- **v2:** Rust, C#, and C++ additional beacons. ([F0107](features/0107-additional-beacon-languages.md))
- **Development strategy:** Build-time obfuscation and runtime stealth are both required.

### 2.5 Module System

- **MVP built-in:** Scanning and enumeration. ([F0022](features/0022-port-scanning-module.md)-[F0037](features/0037-dns-enumeration.md))
- **v2 deferred:** Credential harvesting, lateral movement, process injection. (F0101-F0103)
- **Plugins:** Multi-language API and Python reference. ([F0041](features/0041-plugin-api.md), [F0042](features/0042-python-plugin-reference.md))

### 2.6 Asset Grouping

- Automatic grouping. ([F0031](features/0031-automatic-asset-grouping.md))
- Manual grouping. ([F0032](features/0032-manual-asset-grouping.md))

### 2.7 Database Architecture

- **PostgreSQL:** Persistence foundation is complete with SQLAlchemy sessions, Alembic migrations, pool configuration, model primitives, and CRUD helpers. Domain tables remain scoped to dependent features. ([F0005](features/0005-postgresql-persistence.md))
- **Redis:** Message bus foundation is complete with async client setup, queue, pub/sub, cache, and protected API rate-limit primitives. ([F0006](features/0006-redis-message-bus.md))
- Operator WebSocket fan-out is complete via `events:operator`. Real task queues remain scoped to dependent features. ([F0008](features/0008-operator-websocket-realtime.md), [F0014](features/0014-task-queue.md))

### 2.8 UI Development

- React + TypeScript + Tailwind. ([F0007](features/0007-react-ui-shell.md))
- Stitch MCP is a hard requirement and must be used first for UI development, redesign, restyling, or UI planning work.
- Current routes: `/login`, `/home`, `/projects`, `/recon`, `/beacons`, `/settings`, `/health`.
- `/settings/health` redirects to `/health`.
- Planned disabled side tabs: Reporting, Inventory, Assets.

---

## 3. MVP Feature Matrix

| Feature | ID | Priority | Status |
| :--- | :--- | :--- | :--- |
| **Core Foundation** | | | |
| Docker Compose deploy | F0001 | P0 | Complete |
| CI/CD pipeline | F0002 | P0 | Complete |
| Operator authentication | F0003 | P0 | Complete |
| FastAPI REST API | F0004 | P0 | Complete |
| PostgreSQL database | F0005 | P0 | Complete |
| Redis message bus | F0006 | P0 | Complete |
| React UI shell | F0007 | P0 | Complete |
| Operator WebSocket realtime | F0008 | P0 | Complete |
| Beacon registration | F0009 | P0 | Complete |
| Heartbeat/keepalive | F0010 | P0 | Complete |
| Beacon binary protocol | F0011 | P0 | Planned |
| Beacon WebSocket transport | F0012 | P0 | Planned |
| Beacon HTTP long-poll | F0013 | P0 | Planned |
| Task queue | F0014 | P0 | Planned |
| Go beacon agent | F0015 | P0 | Planned |
| Command execution | F0016 | P0 | Planned |
| Result collection | F0017 | P0 | Planned |
| Interactive shell session | F0018 | P0 | Planned |
| File browser session | F0019 | P0 | Planned |
| Registry editor session | F0020 | P0 | Planned |
| Traffic shaping profiles | F0021 | P0 | Planned |
| Port scanning | F0022 | P0 | Planned |
| Service enumeration | F0023 | P0 | Planned |
| Home overview / dashboard UI | F0024 | P0 | Planned |
| Beacon management UI | F0025 | P0 | Planned |
| Task execution UI | F0026 | P0 | Planned |
| Realtime results UI | F0027 | P0 | Planned |
| Inventory/module browser UI | F0028 | P0 | Planned |
| **Assets & Enum** | | | |
| File transfer | F0029 | P0 | Planned |
| Asset inventory | F0030 | P1 | Planned |
| Automatic asset grouping | F0031 | P1 | Planned |
| Manual asset grouping | F0032 | P1 | Planned |
| Asset management UI | F0033 | P1 | Planned |
| Network topology view | F0034 | P1 | Planned |
| SMB enumeration | F0035 | P1 | Planned |
| LDAP enumeration | F0036 | P1 | Planned |
| DNS enumeration | F0037 | P1 | Planned |
| **Handlers & Plugins** | | | |
| Handler binary (Go) | F0038 | P1 | Planned |
| Handler tunnel to C2 backend | F0039 | P1 | Planned |
| Handler traffic masking | F0040 | P1 | Planned |
| Plugin API | F0041 | P1 | Planned |
| Python plugin reference | F0042 | P1 | Planned |
| Plugin hot-reload | F0043 | P2 | Planned |
| Ad-hoc handler install | F0044 | P2 | Planned |
| Scanner worker registry | F0045 | P1 | Planned |
| Distributed scan orchestration | F0046 | P1 | Planned |
| Beacon pivot scanning/proxying | F0047 | P2 | Planned |
| Handler load balancing | F0109 | P1 | Planned |
| **Post-MVP (v2)** | | | |
| Process injection / token impersonation | F0101 | v2 | Deferred |
| Credential harvesting | F0102 | v2 | Deferred |
| Lateral movement | F0103 | v2 | Deferred |
| Operator MFA | F0104 | v2 | Deferred |
| Multi-role RBAC | F0105 | v2 | Deferred |
| Plugin marketplace | F0106 | v2 | Deferred |
| Additional beacon languages | F0107 | v2 | Deferred |
| Memory-only beacon execution | F0108 | v2 | Deferred |
| RabbitMQ message bus | F0110 | v2 | Deferred |

Full specs: [features/README.md](features/README.md)

---

## 4. Architecture Overview

```text
+-----------------------------------------------------------------+
|                   XERO UI (React + TypeScript)                  |
|  Home | Projects | Recon | Beacons | Reporting* | Inventory*    |
|  Assets* | Settings | Health                                      |
+-----------------------------------------------------------------+
                         |
                         | REST + local JWT
+------------------------v----------------------------------------+
|                 LOCAL XERO BFF (FastAPI)                        |
|  Auth | Protected health | C2 connection setup | Local admin     |
+-----------------------------------------------------------------+
         |                         |
    PostgreSQL                   Redis
         |
         | C2 token flow from Settings
         v
+-----------------------------------------------------------------+
|                 XERO C2 BACKEND (FastAPI)                       |
|  Beacon APIs | Task queues | Embedded handler/scanner | Handlers     |
|  Scanner orchestration | Module orchestration                       |
+-----------------------------------------------------------------+
         |                         |
    PostgreSQL                   Redis
         |
         +-------- Embedded handler path (default) --+--> [ Go Beacons ]
         +-------- External handlers (planned) ------+--> [ Go Beacons ]
         +-------- Embedded scanner path (default) --+--> [ Recon Targets ]
         +-------- External scanners (planned) ------+--> [ Recon Targets ]
         +-------- Beacon pivot path (planned) ------+--> [ Internal Targets ]
```

`*` Planned side tabs are visible but disabled until their features are implemented.

See [architecture/](architecture/README.md).

---

## 5. Directory Structure

Repository root: `xero/`. Implementation: `platform/`. Specs: `spec/`.

See [architecture/directory-structure.md](architecture/directory-structure.md) for full layout.

---

## 6. Implementation Phases

Phases map to [features/README.md](features/README.md) groupings:

### Phase 1: Foundation (Weeks 1-2) - F0001-F0007
### Phase 2: Core C2 (Weeks 3-4) - F0008-F0015
### Phase 3: Tasking & Modules (Weeks 5-6) - F0016-F0028
### Phase 4: Assets & Grouping (Weeks 7-8) - F0030-F0034
### Phase 5: Polish & Integration (Weeks 9-10) - F0029, F0035-F0047, F0109

Each feature must pass unit, integration, and Playwright tests per its spec before marking Complete.

---

## 7. Resolved Decisions

- Local UI/BFF and C2 backend are separate service roles.
- The C2 backend can run locally or remotely.
- The C2 backend is the embedded/default beacon handler and embedded/default scanner when external infrastructure is absent.
- Local administrator account exists by default in development/test and can later be disabled by an admin workflow.
- Health UI is authenticated; root health/readiness endpoints remain public for container checks.
- Stitch MCP is required first for UI development and UI planning.

---

## 8. Terminology & Glossary

| Term | Definition |
| :--- | :--- |
| **Beacon (Agent)** | Payload on an authorized target system |
| **Xero UI** | Operator web dashboard served by the frontend container |
| **Xero BFF** | Local backend-for-frontend service for auth, protected health, and C2 connection setup |
| **Xero C2 Backend** | C2 service managing beacons, tasks, keys, embedded handler/scanner defaults, handler routing, and scanner orchestration |
| **Embedded Handler** | Default beacon connection role inside the C2 backend |
| **External Handler** | Dedicated relay between beacons and C2 backend |
| **Embedded Scanner** | Default scanner role inside the C2 backend |
| **External Scanner** | Dedicated scanner worker registered to C2 |
| **Beacon Pivot** | Later beacon-hosted scanner/proxy route for explicit project scope |
| **Task** | One-shot command or module invocation |
| **Session** | Persistent interactive channel such as shell, file browser, or registry |
| **Profile** | Beacon comms config: sleep, jitter, traffic shaping |
| **mTLS** | Beacon mutual TLS to handlers; not operator MFA |

---

## 9. Feature Specifications

All MVP and v2 capabilities are specified as numbered features in [features/](features/README.md). Each includes staged acceptance criteria, feature-level acceptance criteria, and test plans.

---

## 10. Authorized Use

Xero is intended for **authorized cybersecurity research, defensive security testing, and red-team operations** with explicit written permission from system owners.

Operators must obtain authorization before deploying beacons, handlers, scanners, or pivot routes, use the platform only in authorized environments, and comply with applicable laws and policies.

Unauthorized use is prohibited.
