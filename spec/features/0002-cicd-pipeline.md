# F0002: CI/CD Pipeline

## Metadata
| Field | Value |
|---|---|
| ID | F0002 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001 |

## Summary
GitHub Actions pipeline for backend linting, OpenAPI drift checks, backend tests, frontend lint/test/build, Docker image builds, compose integration tests, and Playwright smoke tests on every PR.

## Requirements
- Lint backend with Ruff.
- Lint frontend with ESLint.
- Run backend unit and behave tests.
- Run frontend unit tests.
- Build backend and frontend Docker images.
- Run integration and Playwright tests against the local UI/BFF compose stack.

## Stages

### Stage 1: Workflow scaffold
**Goal:** Create GitHub Actions workflow triggered on push, PR, and manual dispatch.
**Acceptance Criteria:**
- [x] Workflow file exists at `.github/workflows/ci.yml`.
- [x] Triggers on push to `main`, pull requests to `main`, and workflow dispatch.
- [x] Jobs cover backend, frontend, Docker build, and compose E2E.

### Stage 2: Lint, OpenAPI, and unit tests
**Goal:** Fail fast on code quality, route/schema drift, and unit regressions.
**Acceptance Criteria:**
- [x] Backend lint job passes on clean codebase.
- [x] OpenAPI drift check runs.
- [x] Frontend lint job passes on clean codebase.
- [x] Unit test jobs run pytest and vitest.
- [x] Backend behave tests run.

### Stage 3: Build and E2E
**Goal:** Build images and validate the local UI/BFF compose stack in CI.
**Acceptance Criteria:**
- [x] Docker images build without error.
- [x] Compose integration tests run against `docker compose up -d --build`.
- [x] Playwright smoke suite passes against the frontend container.

## Feature Acceptance Criteria

- [x] CI runs on every PR and blocks merge on failure.
- [x] Pipeline completes in under 15 minutes for typical changes.
- [x] Artifacts include Docker build metadata or failure logs/screenshots.

## Test Plan

### Unit Tests
- [x] Test workflow YAML parses as valid GitHub Actions configuration.
- [x] Test CI script exits non-zero when checks fail.

### System / Integration Tests
- [x] Compose stack starts in CI before integration tests.
- [x] Compose integration tests validate health, auth, and persistence probes.

### Playwright Tests
- [x] CI Playwright job runs login, authenticated home, nav, and protected health smoke tests.
- [x] CI Playwright job captures failure artifacts when smoke tests fail.
