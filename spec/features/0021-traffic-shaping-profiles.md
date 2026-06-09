# F0021: Traffic Shaping Profiles

## Metadata
| Field | Value |
|---|---|
| ID | F0021 |
| Priority | P0 |
| Status | Planned |
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

## Stages

### Stage 1: Profile model
**Goal:** PostgreSQL profiles table and API schemas.
**Acceptance Criteria:**
- [ ] profiles table with name, template, config JSON, version
- [ ] Seed templates for cloudfront and google-analytics
- [ ] Profile assigned to beacon via beacon.profile_id FK

### Stage 2: Beacon application
**Goal:** Go beacon applies profile to HTTP/WS requests.
**Acceptance Criteria:**
- [ ] Beacon reads profile config on registration and heartbeat
- [ ] User-agent and URI path applied to all outbound requests
- [ ] Optional random padding added to request bodies

### Stage 3: Profile management UI
**Goal:** Settings page for profile CRUD and assignment.
**Acceptance Criteria:**
- [ ] List profiles with template type badges
- [ ] Edit profile fields with live preview of HTTP request
- [ ] Assign profile to beacon from beacon detail dropdown

## Feature Acceptance Criteria

- [ ] CloudFront profile produces requests indistinguishable from CDN traffic in lab capture
- [ ] Profile change on beacon takes effect on next heartbeat without restart
- [ ] Operator can create custom profile from template clone

## Test Plan

### Unit Tests
- [ ] test_profile_template_cloudfront_fields
- [ ] test_beacon_applies_user_agent_from_profile
- [ ] test_profile_hot_swap_via_heartbeat_response
- [ ] test_profile_version_increment_on_update
- [ ] test_padding_length_within_configured_range

### System / Integration Tests
- [ ] Assign CloudFront profile; packet capture shows expected headers
- [ ] Update sleep in profile; beacon interval changes within 2 cycles
- [ ] Rollback profile version restores prior configuration

### Playwright Tests
- [ ] Settings profiles page lists CloudFront and Analytics templates
- [ ] Edit profile sleep value and save; success toast shown
- [ ] Assign profile to beacon from beacon detail dropdown
