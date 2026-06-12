# F0105: Multi-Role RBAC

## Metadata
| Field | Value |
|---|---|
| ID | F0105 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0074 |

## Summary
Role-based access control with Operator, Infrastructure Admin, and Developer roles governing C2 API and UI access to tasks, settings, plugins, and infrastructure management. Roles are stored on C2 `operators`; permission middleware runs on the C2 API.

## Requirements
- Roles: operator, infra_admin, developer with permission matrix on C2
- infra_admin: handlers, certs, deployment settings only
- developer: plugin upload, module debug, no task dispatch
- operator: task dispatch, sessions, no infrastructure settings
- Role assignment via C2 admin API; admin role for user management
- JWT role claim on C2 operator tokens used by C2 permission middleware and UI nav filtering
- BFF bootstrap accounts are out of scope for RBAC (setup-only)

## Stages

### Stage 1: Permission model
**Goal:** Define roles, permissions, and C2 middleware.
**Acceptance Criteria:**
- [ ] roles and permissions tables on C2 database with seed data
- [ ] C2 operator JWT includes role claim used by permission middleware
- [ ] Permission decorator on C2 API routes: @requires(Permission.TASK_DISPATCH)

### Stage 2: Role enforcement
**Goal:** Enforce permissions on C2 API and UI routes.
**Acceptance Criteria:**
- [ ] Operator blocked from /api/v1/handlers config endpoints
- [ ] Developer blocked from POST /api/v1/tasks
- [ ] infra_admin blocked from session endpoints

### Stage 3: User management UI
**Goal:** Admin page for role assignment on C2 operators.
**Acceptance Criteria:**
- [ ] Admin creates C2 operators with assigned role via `/settings/access`
- [ ] Role change takes effect on next login
- [ ] UI hides nav items based on C2 operator role permissions

## Feature Acceptance Criteria

- [ ] Operator role cannot access handler configuration API (403)
- [ ] Developer can upload plugin but cannot dispatch tasks
- [ ] infra_admin can rotate certs but cannot open shell sessions

## Test Plan

### Unit Tests
- [ ] test_role_permission_matrix
- [ ] test_c2_jwt_role_claim_in_middleware
- [ ] test_operator_blocked_from_infra_endpoints
- [ ] test_developer_blocked_from_task_dispatch
- [ ] test_ui_nav_filtered_by_role

### System / Integration Tests
- [ ] Login as C2 operator; handler config API returns 403
- [ ] Login as developer; plugin upload succeeds; task dispatch 403
- [ ] Role change; new permissions apply on token refresh

### Playwright Tests
- [ ] Operator login hides Infrastructure settings nav item
- [ ] Developer login shows Plugins but not Tasks nav
- [ ] Admin user management page at `/settings/access` assigns roles
