# F0040: Handler Traffic Masking

## Metadata
| Field | Value |
|---|---|
| ID | F0040 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0038, F0021 |

## Summary
Traffic masking on connection handlers that applies profile-based HTTP header and URI patterns so handler-facing beacon traffic mimics legitimate CDN and analytics services.

## Requirements
- FR-13: Handlers support traffic masking mimicking CDN traffic
- Handler applies same profile templates as beacon profiles
- Inbound beacon requests transformed to match profile pattern
- Outbound handler-to-C2 tunnel traffic separately masked
- Profile assignment per handler instance

## Stages

### Stage 1: Handler profile application
**Goal:** Apply traffic profiles to handler listener.
**Acceptance Criteria:**
- [ ] Handler loads profile from config or C2 assignment
- [ ] Inbound HTTP paths match profile URI patterns
- [ ] Response headers include profile-defined Server and Cache-Control

### Stage 2: CDN mimicry templates
**Goal:** CloudFront and CloudFlare response templates.
**Acceptance Criteria:**
- [ ] CloudFront template returns plausible CDN headers
- [ ] Invalid path returns 404 matching CDN error page style
- [ ] Request logging disabled for masked paths in production mode

### Stage 3: UI assignment
**Goal:** Assign profiles to handlers from settings.
**Acceptance Criteria:**
- [ ] Handler detail shows active traffic profile
- [ ] Profile dropdown in handler configuration form
- [ ] Preview masked request/response in settings

## Feature Acceptance Criteria

- [ ] Handler with CloudFront profile returns CDN-like headers in lab capture
- [ ] Beacon traffic through masked handler indistinguishable from direct CDN
- [ ] Profile change on handler takes effect without handler restart

## Test Plan

### Unit Tests
- [ ] test_handler_applies_profile_headers
- [ ] test_cloudfront_404_response_format
- [ ] test_profile_assignment_api
- [ ] test_inbound_path_matches_profile_uri

### System / Integration Tests
- [ ] Packet capture of handler traffic shows CloudFront headers
- [ ] Assign new profile; next beacon request uses updated headers
- [ ] Masked handler passes beacon task end-to-end

### Playwright Tests
- [ ] Handler settings show active traffic profile name
- [ ] Profile preview panel shows sample request/response
- [ ] Change handler profile; success confirmation shown
