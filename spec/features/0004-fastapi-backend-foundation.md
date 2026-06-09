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
FastAPI application skeleton with routing, middleware, OpenAPI docs, CORS, and structured project layout under platform/backend/.

## Completion Note
Foundation scaffolding was created during F0001-F0003 and formally completed under F0004. Current code exposes the FastAPI app, config loading, CORS, JSON exception handling, OpenAPI generation, public `/health` and `/ready`, protected `/api/v1/health` and `/api/v1/ready`, local auth routes, and C2 connection routes.

## Requirements
- FR-01: Python FastAPI backend
- OpenAPI documentation auto-generated
- Health and readiness endpoints
- Structured app package layout

## Stages

### Stage 1: App skeleton
**Goal:** Create main FastAPI app with lifespan and config.
**Acceptance Criteria:**
- [x] platform/backend/app/main.py exposes FastAPI app
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
