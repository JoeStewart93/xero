# F0021: Traffic Shaping Profiles

## Metadata
| Field | Value |
|---|---|
| ID | F0021 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0015, F0011 |

## Summary
Configurable beacon communication profiles that mimic legitimate traffic patterns (AWS CloudFront, Google Analytics) via user-agent, URI paths, headers, jitter, and sleep schedules.

## Requirements
- SR-04: Beacon traffic configurable to mimic legitimate services
- Profile CRUD API with templates for CloudFront and Google Analytics
- Per-beacon profile assignment with hot-swap via heartbeat response
- Profile fields: sleep, jitter, user_agent, uri_path, headers, padding
- Profile version tracked for rollback

## Approved Implementation Scope
- C2 owns profile CRUD, version snapshots, assignment, and effective profile ACK payloads.
- Runtime C2 assignment is authoritative after registration; compile/build-time fields remain bootstrap defaults.
- Profile updates append immutable version snapshots. Rollback creates a new current version copied from an earlier snapshot.
- Profile config is typed JSON: sleep_seconds, jitter, user_agent, headers, paths, and padding.
- Beacon profile assignment is included in F0021 so hot-swap can be validated; F0025 may later expand management UX.
- Active WebSocket handshake path/header changes apply on reconnect; sleep, jitter, headers for follow-up requests, and padding metadata apply on the next ACK cycle.
- Padding is stored inside encrypted protocol payload metadata and must not be appended to raw binary frames.
- The CloudFront/Google Analytics acceptance evidence is measured by configured user-agent, allowed headers, alias paths, padding bounds, and next-heartbeat hot-swap in the local lab. TLS fingerprinting, DNS, IP reputation, and full CDN indistinguishability remain out of scope for F0021 and belong to later handler masking work.

## Stages

### Stage 1: Profile model
**Goal:** PostgreSQL profiles table and API schemas.
**Acceptance Criteria:**
- [x] profiles table with name, template, config JSON, version
- [x] Seed templates for cloudfront and google-analytics
- [x] Profile assigned to beacon via beacon.profile_id FK

### Stage 2: Beacon application
**Goal:** Go beacon applies profile to HTTP/WS requests.
**Acceptance Criteria:**
- [x] Beacon reads profile config on registration and heartbeat
- [x] User-agent and URI path applied to outbound REST, long-poll, and WebSocket requests
- [x] Optional random padding added inside encrypted protocol payload metadata

### Stage 3: Profile management UI
**Goal:** Settings page for profile CRUD and assignment.
**Acceptance Criteria:**
- [x] List profiles with template type badges
- [x] Edit profile fields with live preview of HTTP request
- [x] Assign profile to beacon from beacon detail dropdown

## Feature Acceptance Criteria

- [x] CloudFront profile produces configured CDN-like user-agent, headers, alias paths, and padding in local lab capture scope
- [x] Profile change on beacon takes effect on next heartbeat without restart
- [x] Operator can create custom profile from template clone

## Test Plan

### Unit Tests
- [x] test_profile_template_cloudfront_fields
- [x] test_beacon_applies_user_agent_from_profile
- [x] test_profile_hot_swap_via_heartbeat_response
- [x] test_profile_version_increment_on_update
- [x] test_padding_length_within_configured_range

### System / Integration Tests
- [x] Assign CloudFront profile; HTTP capture shows expected headers and alias paths
- [x] Update sleep in profile; next ACK carries updated interval
- [x] Rollback profile version restores prior configuration

### Playwright Tests
- [x] Settings profiles page lists CloudFront and Analytics templates
- [x] Edit profile sleep value and save; success toast shown
- [x] Assign profile to beacon from beacon detail dropdown

## Completion Notes
- Implemented C2 traffic profile persistence, immutable versions, template seeding, assignment endpoints, profile ACK payloads, alias routes, and OpenAPI documentation.
- Implemented Go beacon runtime profile application for user-agent, headers, paths, sleep, jitter, and encrypted payload padding.
- Implemented Settings > Profiles CRUD/version UI with request preview and Beacons detail assignment dropdown.
- Rebuilt and restarted the C2 and BFF/frontend Docker stacks, connected the frontend to C2, and passed live F0021 Playwright validation against `http://localhost:3000` and `http://localhost:8001`.
- Validation: `python -m pytest platform/tests/unit/test_c2_api.py -q`; `python -m pytest platform/tests/unit/test_persistence_split.py -q`; `python platform/scripts/openapi.py check c2`; `docker run --rm -v ${PWD}:/src -w /src/platform/beacons/go golang:1.26 go test ./internal/beacon`; `npm --prefix platform/frontend run lint`; `npm --prefix platform/frontend test -- --run src/api.test.ts src/pages/BeaconsPage.test.tsx src/pages/TrafficProfilesPage.test.tsx`; `npm --prefix platform/frontend run build`; `npm --prefix platform/frontend run test:e2e -- --project=chromium e2e/f0021-traffic-profiles.spec.ts`.
