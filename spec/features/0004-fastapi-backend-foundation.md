# F0004: FastAPI Backend Foundation

## Metadata
| Field | Value |
|---|---|
| ID | F0004 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001 |

## Summary
FastAPI application skeleton with routing, middleware, OpenAPI docs, CORS, and structured service layouts. F0048 split the original backend foundation into `platform/services/bff-api/`, `platform/services/c2-api/`, `platform/services/beacon-handler/`, `platform/services/scanner/`, and shared `platform/common/python/xero_common/` code.

## Completion Note
Foundation scaffolding was created during F0001-F0003 and formally completed under F0004. Current code exposes separate FastAPI apps for BFF and C2, config loading, CORS, JSON exception handling, per-service OpenAPI generation, public `/health` and `/ready`, protected BFF `/api/v1/health` and `/api/v1/ready`, local auth routes, C2 connection routes, and handler/scanner health scaffolds.

## Requirements
- FR-01: Python FastAPI backend
- OpenAPI documentation auto-generated
- Health and readiness endpoints
- Structured app package layout

## Stages

### Stage 1: App skeleton
**Goal:** Create main FastAPI app with lifespan and config.
**Acceptance Criteria:**
- [x] BFF and C2 service packages expose FastAPI apps
- [x] Config loaded from environment via config.py
- [x] GET /health returns 200

### Stage 2: Routing and middleware
**Goal:** Wire API router, CORS, and error handlers.
**Acceptance Criteria:**
- [x] API routes mounted under /api/v1
- [x] CORS configured for frontend origin
- [x] Unhandled exceptions return JSON error response

### Stage 3: OpenAPI and testing hooks
**Goal:** Expose docs and test fixtures.
**Acceptance Criteria:**
- [x] /docs serves OpenAPI UI
- [x] pytest fixtures provide TestClient
- [x] Readiness endpoint checks downstream deps when available

## Feature Acceptance Criteria

- [x] Backend starts via uvicorn in Docker and locally
- [x] OpenAPI spec documents all registered routes
- [x] Health endpoint used by compose healthcheck

## Test Plan

### Unit Tests
- [x] test_health_endpoint returns 200
- [x] test_api_v1_prefix on registered routes
- [x] test_cors_headers on preflight request

### System / Integration Tests
- [x] Backend container starts and passes healthcheck in compose
- [x] OpenAPI /docs accessible from host

### Playwright Tests
- [x] Frontend health indicator shows backend reachable after login
- [x] API docs link in settings is not exposed; `/docs` host accessibility is covered by integration tests

## Follow-up (F0074)

- C2 API gains operator auth routes (`POST /api/v1/auth/login`, `GET /api/v1/me`, `POST /api/v1/auth/password`).
- BFF auth routes remain for bootstrap scope only; `POST /api/v1/c2/connect` is removed from C2.
