# F0005: PostgreSQL Persistence

## Metadata
| Field | Value |
|---|---|
| ID | F0005 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001, F0004 |

## Summary
PostgreSQL integration with SQLAlchemy models, Alembic migrations, connection pooling, request-scoped sessions, and reusable CRUD foundations for persistent backend entities.

## Current Implementation Note
F0005 is complete as the persistence foundation. The backend has configured SQLAlchemy engine/session factories, explicit PostgreSQL pool settings, Alembic migrations, Docker entrypoint migration execution, reusable UUID/timestamp model primitives, generic CRUD helpers, rollback semantics, and ORM-backed persistence verification across container restarts. F0008 adds the minimal `beacons` table needed for realtime verification; full beacon/session/task/asset/handler/plugin persistence remains owned by later feature specs.

## Requirements
- FR-03: PostgreSQL for beacons, sessions, task history
- Alembic migrations for schema versioning
- Connection pooling and session management

## Stages

### Stage 1: Database connection
**Goal:** Configure SQLAlchemy engine and session factory.
**Acceptance Criteria:**
- [x] database.py connects using DATABASE_URL env
- [x] Connection pool sized for backend workload
- [x] Sessions scoped per request

### Stage 2: Migration framework
**Goal:** Initialize Alembic and baseline migration.
**Acceptance Criteria:**
- [x] alembic/ directory with env.py
- [x] Initial migration creates base schema
- [x] migrate command runs in Docker entrypoint

### Stage 3: CRUD patterns
**Goal:** Establish repository/CRUD patterns for entities.
**Acceptance Criteria:**
- [x] Base model with id, created_at, updated_at
- [x] CRUD helpers for create/read/update/delete
- [x] Transaction rollback on error

## Feature Acceptance Criteria

- [x] Migrations apply cleanly on fresh and existing databases
- [x] Backend persists and retrieves records across restarts
- [x] No raw SQL required for standard entity operations

## Test Plan

### Unit Tests
- [x] test_session_factory creates and closes sessions
- [x] test_migration_upgrade_head on sqlite test db
- [x] test_crud_create_read_update_delete

### System / Integration Tests
- [x] Run migrations in compose; backend stores and retrieves test record
- [x] Restart postgres; data persists

### Playwright Tests
- [x] Not applicable for F0005 because no user-facing persistence workflow is introduced; UI persistence checks belong with later UI/domain features.
