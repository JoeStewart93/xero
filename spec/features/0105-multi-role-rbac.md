# F0105: Multi-Role RBAC

## Metadata
| Field | Value |
|---|---|
| ID | F0105 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0003 |

## Summary
Role-based access control with Operator, Infrastructure Admin, and Developer roles governing API and UI access to tasks, settings, plugins, and infrastructure management.

## Requirements
- Roles: operator, infra_admin, developer with permission matrix
- infra_admin: handlers, certs, deployment settings only
- developer: plugin upload, module debug, no task dispatch
- operator: task dispatch, sessions, no infrastructure settings
- Role assignment via admin API; admin role for user management

## Stages

### Stage 1: Permission model
**Goal:** Define roles, permissions, and middleware.
**Acceptance Criteria:**
- [ ] roles and permissions tables with seed data
- [ ] JWT includes role claim used by permission middleware
- [ ] Permission decorator on API routes: @requires(Permission.TASK_DISPATCH)

### Stage 2: Role enforcement
**Goal:** Enforce permissions on API and UI routes.
**Acceptance Criteria:**
- [ ] Operator blocked from /api/v1/handlers config endpoints
- [ ] Developer blocked from POST /api/v1/tasks
- [ ] infra_admin blocked from session endpoints

### Stage 3: User management UI
**Goal:** Admin page for role assignment.
**Acceptance Criteria:**
- [ ] Admin creates users with assigned role
- [ ] Role change takes effect on next login
- [ ] UI hides nav items based on role permissions

## Feature Acceptance Criteria

- [ ] Operator role cannot access handler configuration API (403)
- [ ] Developer can upload plugin but cannot dispatch tasks
- [ ] infra_admin can rotate certs but cannot open shell sessions

## Test Plan

### Unit Tests
- [ ] test_role_permission_matrix
- [ ] test_jwt_role_claim_in_middleware
- [ ] test_operator_blocked_from_infra_endpoints
- [ ] test_developer_blocked_from_task_dispatch
- [ ] test_ui_nav_filtered_by_role

### System / Integration Tests
- [ ] Login as operator; handler config API returns 403
- [ ] Login as developer; plugin upload succeeds; task dispatch 403
- [ ] Role change; new permissions apply on token refresh

### Playwright Tests
- [ ] Operator login hides Infrastructure settings nav item
- [ ] Developer login shows Plugins but not Tasks nav
- [ ] Admin user management page assigns roles
