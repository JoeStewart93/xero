# F0024: Home Overview / Dashboard UI

## Metadata
| Field | Value |
|---|---|
| ID | F0024 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0007, F0008, F0009 |

## Summary
Home overview/dashboard experience showing at-a-glance beacon statistics, recent task activity, C2 connection status, system health, and quick-action shortcuts for common operator workflows.

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
- [ ] Home route at `/home` remains the default post-login landing
- [ ] Summary cards: total, online, offline beacon counts
- [ ] Recent activity feed with task and beacon events

### Stage 2: Data fetching
**Goal:** Wire dashboard to REST and WebSocket data sources.
**Acceptance Criteria:**
- [ ] Initial load via GET /api/v1/dashboard/summary
- [ ] WebSocket events update cards and feed in real time
- [ ] Loading skeletons shown during initial fetch

### Stage 3: Health, C2 connection, and quick actions
**Goal:** System health indicators and action buttons.
**Acceptance Criteria:**
- [ ] Health panel shows green/amber/red per dependency
- [ ] C2 connection state shows connected/disconnected and links to Settings
- [ ] Quick action buttons navigate to relevant pages
- [ ] Empty state guidance when no beacons registered

## Feature Acceptance Criteria

- [ ] Dashboard loads within 2s on warm stack with accurate beacon counts
- [ ] Beacon check-in updates online count without page refresh
- [ ] Health panel reflects actual postgres/redis connectivity

## Test Plan

### Unit Tests
- [ ] test_dashboard_summary_api_response_shape
- [ ] test_dashboard_card_renders_counts
- [ ] test_websocket_event_updates_card_state
- [ ] test_health_panel_status_mapping
- [ ] test_empty_state_renders_when_no_beacons

### System / Integration Tests
- [ ] GET /api/v1/dashboard/summary returns counts matching database
- [ ] Beacon heartbeat updates dashboard via WebSocket event
- [ ] Stop redis; health panel shows degraded status

### Playwright Tests
- [ ] Login redirects to `/home` with summary cards visible
- [ ] Register beacon; online count increments on dashboard
- [ ] Recent tasks widget shows latest completed task
