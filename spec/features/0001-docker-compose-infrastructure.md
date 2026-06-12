# F0001: Docker Compose Infrastructure

## Metadata
| Field | Value |
|---|---|
| ID | F0001 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | - |

## Summary
Provide reproducible local and lab deployment stacks via Docker Compose. The primary stack runs the local UI/BFF, PostgreSQL, Redis, and frontend. A separate compose file runs the optional local C2 backend stack so C2 logic can run locally or remotely. F0048 later split backend code and compose services into explicit BFF/C2/handler/scanner service boundaries.

## Requirements
- GR-01: All local services deployable via Docker Compose.
- `platform/docker-compose.bff.yml` starts local BFF API, frontend, BFF PostgreSQL, and BFF Redis; `platform/docker-compose.yml` remains a temporary compatibility alias.
- `platform/docker-compose.c2.yml` starts a separate C2 API, C2 PostgreSQL, and C2 Redis.
- `platform/docker-compose.handler.yml` and `platform/docker-compose.scanner.yml` start health/readiness scaffolds for future external services.
- PostgreSQL and Redis containers use persistent named volumes.
- `.env.example` documents defaults for both stacks.
- Healthchecks exist for all compose services.

## Stages

### Stage 1: Local UI/BFF compose scaffold
**Goal:** Define services, networks, and volumes for the local UI/BFF stack.
**Acceptance Criteria:**
- [x] `docker-compose.bff.yml` defines `bff-postgres`, `bff-redis`, `bff-api`, and `frontend` services.
- [x] BFF service uses its own `platform/services/bff-api` build context.
- [x] Services share a dedicated bridge network.
- [x] Named volumes persist PostgreSQL and Redis data.

### Stage 2: Separate C2 backend compose scaffold
**Goal:** Define a second stack for C2 backend deployment.
**Acceptance Criteria:**
- [x] `docker-compose.c2.yml` defines `c2-postgres`, `c2-redis`, and `c2-api`.
- [x] C2 service uses its own `platform/services/c2-api` build context.
- [x] C2 stack uses separate named volumes from the local UI/BFF stack.
- [x] C2 backend exposes `${C2_BACKEND_PORT:-8001}`.

### Stage 3: Environment configuration
**Goal:** Document and wire environment variables for both stacks.
**Acceptance Criteria:**
- [x] `.env.example` lists local BFF variables.
- [x] `.env.example` lists C2 backend variables, including `C2_CONNECT_PASSWORD`.
- [x] Frontend receives `VITE_API_BASE_URL` and `VITE_DEFAULT_C2_BASE_URL`.
- [x] BFF and C2 services connect to their own Postgres and Redis services via compose service names.

### Stage 4: Health and startup ordering
**Goal:** Ensure dependent services wait for database/cache readiness.
**Acceptance Criteria:**
- [x] Postgres healthcheck passes before BFF/C2 API starts.
- [x] Redis healthcheck passes before BFF/C2 API starts.
- [x] BFF/C2 API healthchecks use public `GET /ready`.
- [x] Frontend healthcheck uses public `GET /login`.
- [x] `docker compose -f docker-compose.bff.yml up` brings the local UI/BFF stack to healthy state.

## Feature Acceptance Criteria

- [x] `docker compose -f docker-compose.bff.yml up --build` starts the local Xero UI/BFF stack.
- [x] `docker compose -f docker-compose.c2.yml up --build` starts the local C2 backend stack.
- [x] All local stack containers report healthy within 60 seconds on a clean machine.
- [x] Data persists across container restarts via volumes.

## Test Plan

### Unit Tests
- [x] Validate compose schema, services, ports, healthchecks, networks, and volumes.
- [x] Validate BFF and C2 compose files use separate service Dockerfiles.
- [x] Validate `.env.example` contains variables consumed by compose/backend/frontend.

### System / Integration Tests
- [x] `docker compose config` succeeds.
- [x] `docker compose -f docker-compose.bff.yml up -d --build`; all local services reach healthy status.
- [x] Restart Postgres; backend readiness recovers after dependency recovery.
- [x] Stop and start stack; persisted probe data survives.

### Playwright Tests
- [x] Login page loads without backend connection errors.
- [x] Unauthenticated `/health` redirects to login.
- [x] Authenticated `/health` shows green status for backend, Postgres, and Redis dependencies.

## Follow-up (F0074)

- Replace `C2_CONNECT_PASSWORD` with `C2_ADMIN_USERNAME` / `C2_ADMIN_PASSWORD` in `.env.example` when F0074 is implemented.
- Document removal of the shared C2 connect password; operators authenticate with C2 credentials instead.
