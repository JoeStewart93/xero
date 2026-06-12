# F0074: C2 Operator Authentication

## Metadata
| Field | Value |
|---|---|
| ID | F0074 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 1 (auth hardening) |
| Depends on | F0048, F0008, F0009 |
| Supersedes (operational auth) | F0003 platform operator scope |

## Summary
C2 becomes the source of truth for operator identity. Add C2 `operators` persistence, login/token issuance, operator-scoped JWT authorization on all current C2 bearer-protected routes and `/ws/operator`, basic admin operator CRUD, and UI login that authenticates against C2 when a backend URL is configured. Deprecate anonymous `kind: c2-connect` tokens and the Settings C2 password connect workflow.

## Requirements
- C2-owned `operators` table (username, password_hash, role, is_enabled, created_at, updated_at) in C2 Postgres/Alembic.
- Seed C2 admin from `C2_ADMIN_USERNAME` / `C2_ADMIN_PASSWORD`; reject defaults outside development/test (mirror BFF pattern in `platform/services/c2-api/xero_c2/config.py`).
- `POST /api/v1/auth/login`, `GET /api/v1/me`, `POST /api/v1/auth/password` on C2 API.
- Operator JWT claims: `operator_id`, `sub` (username), `role`, `kind: operator-session` (new constant alongside existing `C2_TOKEN_KIND` in `platform/common/python/xero_common/security.py`).
- Replace `authorize_c2_token()` validation to require operator JWTs; remove `POST /api/v1/c2/connect`.
- WebSocket `/ws/operator` and `RealtimePrincipal` carry operator identity.
- Admin-only operator management API: list/create/update/disable operators (foundation for F0105 user management UI).
- BFF local `admin` role narrowed to **bootstrap** scope (rename role value or document equivalent permission set).
- UI unified login: when `VITE_DEFAULT_C2_BASE_URL` or stored C2 URL exists, login hits C2; otherwise bootstrap BFF login for setup.
- Remove Settings C2 password field; connection status derived from operator session via `GET /api/v1/me` or session check endpoint.
- Non-development deployments must override C2 admin seed credentials (SR-05 extension).
- Remove `C2_CONNECT_PASSWORD` from `.env.example` and compose documentation; operators authenticate with C2 credentials instead.

## Stages

### Stage 1: C2 operator persistence and login
**Goal:** Create C2 operators table, seed admin account, and expose login endpoints.
**Acceptance Criteria:**
- [ ] C2 Alembic migration creates `operators` table with username, password hash, role, enabled flag, and timestamps.
- [ ] Startup seed creates C2 admin from `C2_ADMIN_USERNAME` / `C2_ADMIN_PASSWORD` when missing.
- [ ] Passwords are never stored in plaintext.
- [ ] Default C2 admin credentials are rejected outside development/test modes.
- [ ] `POST /api/v1/auth/login` accepts username/password and returns operator JWT, expiration, token type, and public operator metadata.
- [ ] Invalid credentials return 401; disabled operators cannot authenticate.
- [ ] `GET /api/v1/me` returns authenticated operator metadata.
- [ ] `POST /api/v1/auth/password` requires current password and updates BCrypt hash.

### Stage 2: Operator-scoped C2 authorization
**Goal:** Require operator JWT on all C2 bearer-protected routes and WebSocket connections; remove anonymous connect flow.
**Acceptance Criteria:**
- [ ] All routes currently calling `authorize_c2_token()` accept operator JWTs with `kind: operator-session`.
- [ ] `/ws/operator` rejects anonymous `kind: c2-connect` tokens; `RealtimePrincipal` includes operator_id and username.
- [ ] `POST /api/v1/c2/connect` and `create_c2_access_token()` anonymous path are removed.
- [ ] `platform/docs/api/c2.openapi.yaml` reflects auth routes and removed connect route.
- [ ] No automatic token migration; operators must re-login after upgrade.

### Stage 3: BFF bootstrap scope
**Goal:** Narrow BFF local auth to first-run setup and local health only.
**Acceptance Criteria:**
- [ ] BFF `users` table remains for bootstrap accounts only; platform user management is not on BFF.
- [ ] BFF `admin` (bootstrap) role can access BFF health/readiness and C2 URL configuration surfaces only.
- [ ] BFF bootstrap role cannot satisfy operational C2-backed UI routes (Beacons, Infrastructure, etc.).
- [ ] BFF `operator/operator_password` dev seed is removed or scoped equivalent to bootstrap in development/test.
- [ ] F0003 Scope Evolution documents post-F0074 bootstrap semantics.

### Stage 4: Unified UI login and connect removal
**Goal:** Single login flow against C2 when configured; remove separate Settings connect password workflow.
**Acceptance Criteria:**
- [ ] Login page authenticates against C2 when `VITE_DEFAULT_C2_BASE_URL` or stored C2 URL is configured.
- [ ] Login page falls back to BFF bootstrap login when no C2 URL is configured.
- [ ] Operator JWT from C2 login becomes the C2 session token (merged auth/C2 connection context).
- [ ] Settings Infrastructure panel shows backend URL, worker inventory, and connection status without a password field.
- [ ] Operational routes require C2 operator session; bootstrap admin is redirected or blocked from operational pages.
- [ ] C2 operator login reaches Beacons and Infrastructure without a separate connect step.

## Feature Acceptance Criteria

- [ ] C2 operator can log in via UI and receive an operator-scoped session token.
- [ ] Operator JWT grants access to beacons, infrastructure workers, protocol endpoints, and `/ws/operator`.
- [ ] Bootstrap BFF admin can configure C2 URL but cannot access operational C2-backed workflows.
- [ ] Shared `C2_CONNECT_PASSWORD` connect flow is removed from UI and API.
- [ ] C2 admin can create, disable, and update operators via admin API.
- [ ] Non-development deployments reject default C2 admin seed credentials.

## Test Plan

### Unit Tests
- [ ] Test C2 password hash and verify BCrypt round-trip.
- [ ] Test operator JWT create/decode with `kind: operator-session`.
- [ ] Test C2 login invalid credentials returns 401.
- [ ] Test disabled C2 operator cannot authenticate.
- [ ] Test default C2 admin seed rejection outside dev/test.
- [ ] Test `authorize_c2_token()` rejects anonymous `c2-connect` tokens.
- [ ] Test operator CRUD admin endpoints enforce admin role.
- [ ] Test bootstrap BFF role scope restrictions.

### System / Integration Tests
- [ ] C2 login via API; use token to access `/api/v1/beacons`.
- [ ] C2 login via API; use token to open `/ws/operator`.
- [ ] Removed `/api/v1/c2/connect` returns 404 or is absent from OpenAPI.
- [ ] Bootstrap BFF login cannot access C2 operational endpoints without C2 operator session.
- [ ] C2 stack compose health and operator login work with `C2_ADMIN_*` env vars.

### Playwright Tests
- [ ] Bootstrap login can reach Settings but not Beacons operational data.
- [ ] C2 operator login reaches Beacons without separate Settings connect step.
- [ ] Login with invalid C2 credentials shows error message.
- [ ] Settings C2 panel shows connected status after operator login (no password field).
- [ ] New spec: `f0074-c2-operator-authentication.spec.ts`.

## Out Of Scope

- Full permission matrix and nav filtering. See [F0105](0105-multi-role-rbac.md).
- TOTP/WebAuthn MFA. See [F0104](0104-operator-mfa.md) (retargeted to C2).
- BFF-as-auth-proxy. UI continues direct-to-C2 for operational APIs per [F0048](0048-service-boundary-refactor.md).
