# F0024: Home Overview / Dashboard UI

## Metadata
| Field | Value |
|---|---|
| ID | F0024 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0007, F0008, F0009, F0014 |
| Story Points | 5 |

## Summary
Home overview/dashboard experience showing at-a-glance beacon statistics, recent task activity, C2 connection status, system health, and quick-action shortcuts for common operator workflows.

## Value
Gives operators a fast, trustworthy landing view for C2 posture, beacon coverage, recent task activity, and next actions without forcing them to jump through multiple pages after login.

## Use Cases
- Operator logs in and confirms the C2 stack, realtime channel, and dependency health are usable.
- Operator sees total, online, and offline beacon counts before starting tasking or recon.
- Operator reviews the latest task and beacon activity after a live operation or stack restart.
- Operator jumps directly to tasking, offline beacon review, or Settings from the Home route.

## Assumptions
- `/home` remains the canonical post-login landing route; `/dashboard` continues to redirect to `/home`.
- Operational dashboard data is owned by C2 because beacons, tasks, task events, and C2 readiness live there.
- Local BFF readiness remains a separate frontend health input and is not proxied through the C2 dashboard endpoint.
- Quick actions are route intents only in this feature; Home will not create or dispatch tasks until F0026.
- Stitch was attempted first for UI planning. Project `projects/10217282131430809998` was created, but screen generation was blocked by missing Stitch OAuth credentials.
- Context7 React/FastAPI documentation lookup was attempted and blocked by an expired OAuth token, so implementation follows existing repo patterns.

## Implementation Scope
- Add C2 `GET /api/v1/dashboard/summary` with beacon counts, latest tasks, normalized activity, and C2 health.
- Expand the existing `HomePage` instead of introducing a separate dashboard surface.
- Keep dashboard event reduction feature-local so the shared realtime provider remains transport-focused.
- Update API specs and docs when the endpoint is added.

## Requirements
- FR-08 foundation: summary cards for beacon counts by status
- Recent tasks widget with last 10 tasks and status
- System health panel: local BFF, postgres, redis, and C2 connection status
- Real-time updates via operator WebSocket without page refresh
- Quick actions: new task, view offline beacons, open settings

## Stages

### Stage 1: Dashboard layout
**Goal:** Expand the existing Home route with a production dashboard layout.
**Acceptance Criteria:**
- [x] Home route at `/home` remains the default post-login landing
- [x] Summary cards: total, online, offline beacon counts
- [x] Recent activity feed with task and beacon events

### Stage 2: Data fetching
**Goal:** Wire dashboard to REST and WebSocket data sources.
**Acceptance Criteria:**
- [x] Initial load via GET /api/v1/dashboard/summary
- [x] WebSocket events update cards and feed in real time
- [x] Loading skeletons shown during initial fetch

### Stage 3: Health, C2 connection, and quick actions
**Goal:** System health indicators and action buttons.
**Acceptance Criteria:**
- [x] Health panel shows green/amber/red per dependency
- [x] C2 connection state shows connected/disconnected and links to Settings
- [x] Quick action buttons navigate to relevant pages
- [x] Empty state guidance when no beacons registered

## Feature Acceptance Criteria

- [x] Dashboard loads within 2s on warm stack with accurate beacon counts
- [x] Beacon check-in updates online count without page refresh
- [x] Health panel reflects actual postgres/redis connectivity

## Test Plan

### Unit Tests
- [x] test_dashboard_summary_api_response_shape
- [x] test_dashboard_card_renders_counts
- [x] test_websocket_event_updates_card_state
- [x] test_health_panel_status_mapping
- [x] test_empty_state_renders_when_no_beacons

### System / Integration Tests
- [x] GET /api/v1/dashboard/summary returns counts matching database
- [x] Beacon heartbeat updates dashboard via WebSocket event
- [x] Stop redis; health panel shows degraded status

### Playwright Tests
- [x] Login redirects to `/home` with summary cards visible
- [x] Register beacon; online count increments on dashboard
- [x] Recent tasks widget shows latest completed task

## Completion Notes

- Added C2-owned `GET /api/v1/dashboard/summary` with beacon counts, recent tasks, normalized activity, generated timestamp, and C2 dependency health.
- Expanded the existing `/home` route into the operator dashboard while keeping `/dashboard` as a redirect to `/home`.
- Connected the dashboard to the C2 operator WebSocket stream for beacon registration, status changes, task events, and system realtime events.
- Shared the health normalization logic between Home and Health pages while keeping dashboard event reduction feature-local.
- Updated the exported C2 OpenAPI document for the new dashboard endpoint.

## Validation Evidence

- `python -m pytest platform/tests/unit/test_c2_api.py -q`
- `python -m pytest platform/tests/unit/test_persistence_split.py -q`
- `npm --prefix platform/frontend test -- --run`
- `npm --prefix platform/frontend run lint`
- `npm --prefix platform/frontend run build`
- `python platform/scripts/openapi.py check c2`
- `docker compose -f platform/docker-compose.c2.yml up -d --build --force-recreate`
- `docker compose -f docker-compose.bff.yml up -d --build --force-recreate` from `platform/`
- Connected C2 readiness checks for `http://localhost:8001/ready` and authenticated BFF `http://localhost:8000/api/v1/ready`
- `PLAYWRIGHT_BASE_URL=http://localhost:3000 PLAYWRIGHT_C2_BASE_URL=http://localhost:8001 C2_CONNECT_PASSWORD=c2_password npm run test:e2e -- --project=chromium e2e/f0024-dashboard.spec.ts`
- Browser sanity checked desktop and mobile `/home` with C2 connected to `http://localhost:8001`.

## Maintainability Review

No separate refactor round is required. The backend dashboard aggregation lives in `xero_c2.dashboard`, schemas are typed in the shared C2 schema module, the frontend API types remain in `api.ts`, and dashboard-specific realtime reduction is isolated in `dashboardEvents.ts` so the shared realtime provider stays transport-focused.
