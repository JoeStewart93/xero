# F0007: React UI Shell

## Metadata
| Field | Value |
|---|---|
| ID | F0007 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001, F0003 |

## Summary
React + TypeScript + Tailwind application shell with routing, auth guard, layout, and API client foundation.

## Current Implementation Note
The frontend includes a Vite/React/TypeScript/Tailwind foundation, dark Xero visual system, `/login`, protected operator routes, local auth storage, JWT-aware API helpers, C2 connection storage, and a left side rail. The shell now exposes routeable UI stubs for Exploits, Payloads, Assets, Reports, and Loot, with Inventory under Assets. F0007 is complete as the React UI shell foundation; later UI features own their domain pages and data workflows.

## Requirements
- FR-06: React + TypeScript + Tailwind UI
- FR-07: Connect to BFF/C2 services over TLS in deployed environments
- Login page and authenticated layout
- Navigation for Home, Projects, Recon, Beacons, Exploits, Payloads, Assets, Reports, Loot, Settings, and separated Health/Realtime utility surfaces

## Stages

### Stage 1: Project scaffold
**Goal:** Create Vite/React/TS/Tailwind project under platform/frontend/.
**Acceptance Criteria:**
- [x] npm run dev starts dev server
- [x] Tailwind styles applied globally
- [x] TypeScript strict mode enabled

### Stage 2: Routing and layout
**Goal:** Implement React Router with auth guard.
**Acceptance Criteria:**
- [x] Public /login and protected routes
- [x] AppLayout with sidebar navigation
- [x] 404 page for unknown routes

### Stage 3: API client
**Goal:** Create axios/fetch wrapper with JWT injection.
**Acceptance Criteria:**
- [x] api.ts attaches Bearer token from auth store
- [x] 401 response triggers logout redirect
- [x] Base URL from environment

## Feature Acceptance Criteria

- [x] Operator sees login page when unauthenticated
- [x] Authenticated user sees shell with navigation placeholders
- [x] UI builds and runs in Docker frontend container

## Test Plan

### Unit Tests
- [x] Auth store sets and clears JWT
- [x] API client attaches Authorization header
- [x] ProtectedRoute redirects when no token

### System / Integration Tests
- [x] Frontend container serves static build via nginx/node
- [x] Login flow obtains JWT and stores in client

### Playwright Tests
- [x] Navigate to /; unauthenticated user redirected to /login
- [x] After login, sidebar shows all nav items
- [x] Logout returns user to login page

## Follow-up (F0074)

- Login becomes dual-path: C2 operator auth when C2 URL is configured, BFF bootstrap auth otherwise.
- C2 connection storage merges with operator auth session; separate Settings connect password flow is removed.
- Route guards distinguish bootstrap session vs C2 operator session for operational pages.
