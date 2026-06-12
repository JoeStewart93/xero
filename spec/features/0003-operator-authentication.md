# F0003: Operator Authentication

## Metadata
| Field | Value |
|---|---|
| ID | F0003 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001 plus auth persistence scaffolding |
| Superseded by (operational auth) | [F0074](0074-c2-operator-authentication.md) |

## Summary
Username/password authentication with BCrypt-hashed PostgreSQL user records and JWT session tokens for local Xero UI/BFF access. This feature also seeds a default development operator and a default local administrator account.

## Scope Evolution

F0003 delivered **BFF-local bootstrap authentication** only. Current implementation lives in `platform/services/bff-api/xero_bff/main.py`.

Platform operator identity, C2 session authority, and user management move to **[F0074](0074-c2-operator-authentication.md)** on the C2 API. Post-F0074 behavior:

- `admin/admin` (BFF bootstrap admin) remains for first-run C2 URL configuration and BFF health access but **loses operational platform authority** (Beacons, Infrastructure, worker pairing, etc.).
- BFF `operator/operator_password` dev seed is **removed or scoped equivalent to bootstrap** in development/test; see F0074 Stage 3.
- Operational UI login authenticates against C2 when a backend URL is configured; the separate Settings C2 connect password workflow is removed by F0074.

## Requirements
- FR-02: JWT authentication for local operator access.
- BCrypt password hashing in PostgreSQL.
- Default development operator: `operator/operator_password`.
- Default local administrator: `admin/admin`.
- Local admin account is enabled by default and can be disabled by a later admin workflow.
- Configurable JWT expiration.
- Root `/health` and `/ready` remain public for container healthchecks.
- UI-facing `/health` route and `/api/v1/*` operator routes require JWT, except C2 connection endpoints on C2 backends.

## Stages

### Stage 1: User model and seed
**Goal:** Create local users table and development seed accounts.
**Acceptance Criteria:**
- [x] `users` table has username, password hash, role, enabled flag, created timestamp, and updated timestamp.
- [x] Startup seed creates operator from `OPERATOR_USERNAME` / `OPERATOR_PASSWORD` when missing.
- [x] Startup seed creates local admin from `LOCAL_ADMIN_USERNAME` / `LOCAL_ADMIN_PASSWORD` when missing.
- [x] Passwords are never stored in plaintext.
- [x] Default auth secrets are rejected outside development/test modes.

### Stage 2: Login and token issuance
**Goal:** Implement local login endpoint returning JWT.
**Acceptance Criteria:**
- [x] `POST /auth/login` accepts username/password.
- [x] Invalid credentials return 401.
- [x] Disabled users cannot authenticate.
- [x] Valid login returns JWT, expiration, token type, and public operator metadata.

### Stage 3: Protected local routes
**Goal:** Enforce JWT on local operator API and frontend health routes.
**Acceptance Criteria:**
- [x] Missing token returns 401 for protected API routes.
- [x] Expired token returns 401.
- [x] Valid token grants access to `/api/v1/me`.
- [x] Valid token grants access to `/api/v1/health` and `/api/v1/ready`.
- [x] Unauthenticated frontend `/health` redirects to `/login`.

### Stage 4: Password update
**Goal:** Allow authenticated operators to change their local password.
**Acceptance Criteria:**
- [x] `POST /api/v1/auth/password` requires current password.
- [x] Invalid current password returns 401.
- [x] Valid password change updates only the BCrypt hash.
- [x] Old password no longer authenticates after change.

## Feature Acceptance Criteria

- [x] Operator can log in via UI and receive a session token.
- [x] Default local admin `admin/admin` can log in in development/test defaults.
- [x] Protected UI routes redirect unauthenticated users to `/login`.
- [x] Authenticated login lands on `/home`.
- [x] Password change updates hash without plaintext exposure.

## Test Plan

### Unit Tests
- [x] Test password hash and verify BCrypt round-trip.
- [x] Test JWT create/decode with expiration.
- [x] Test login invalid credentials returns 401.
- [x] Test disabled operator cannot authenticate.
- [x] Test default local admin login.
- [x] Test protected route requires token.
- [x] Test protected health/readiness require token.
- [x] Test password change invalidates old password.

### System / Integration Tests
- [x] Login via API; use token to access `/api/v1/me`.
- [x] Login via API; use token to access `/api/v1/me`.
- [x] Unauthenticated protected health returns 401.
- [x] Expired token rejected on subsequent requests.

### Playwright Tests
- [x] Login with valid operator credentials redirects to `/home`.
- [x] Login with default local admin credentials redirects to `/home`.
- [x] Login with invalid credentials shows error message.
- [x] Unauthenticated `/projects` redirects to login.
- [x] Unauthenticated `/health` redirects to login.
- [x] Authenticated `/health` shows dependency status.
