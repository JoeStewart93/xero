# F0101: Process Injection Token Impersonation

## Metadata
| Field | Value |
|---|---|
| ID | F0101 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015 |

## Summary
v2 beacon capability for process injection and Windows token impersonation enabling elevated execution context for post-exploitation modules in authorized engagements.

## Requirements
- FR-14: Process injection and token impersonation (v2)
- Injection techniques: remote thread, process hollowing (configurable)
- Token impersonation via stolen or duplicated tokens
- Operator authorization gate required before enabling feature
- Audit log of all injection and impersonation events

## Stages

### Stage 1: Injection framework
**Goal:** Beacon module for process injection primitives.
**Acceptance Criteria:**
- [ ] inject module with target_pid, technique, payload args
- [ ] Techniques pluggable via technique registry
- [ ] Injection failure returns structured error code

### Stage 2: Token impersonation
**Goal:** Steal/duplicate token and impersonate for task execution.
**Acceptance Criteria:**
- [ ] impersonate module with target_pid or token_handle args
- [ ] Subsequent tasks run under impersonated token context
- [ ] Revert to original token after task completion

### Stage 3: Authorization gate
**Goal:** Require explicit operator enablement per engagement.
**Acceptance Criteria:**
- [ ] Feature disabled by default in v2 config
- [ ] Enable requires operator acknowledgment of authorization
- [ ] All injection events logged with operator ID and timestamp

## Feature Acceptance Criteria

- [ ] Injection module executes payload in target process on lab Windows VM
- [ ] Token impersonation enables access to otherwise denied resources in lab
- [ ] Feature remains disabled until operator explicitly enables

## Test Plan

### Unit Tests
- [ ] test_injection_technique_registry
- [ ] test_impersonate_token_lifecycle
- [ ] test_feature_disabled_by_default
- [ ] test_authorization_gate_required
- [ ] test_injection_audit_log

### System / Integration Tests
- [ ] Enable feature; inject into lab process; payload executes
- [ ] Impersonate SYSTEM token; file access task succeeds
- [ ] Disable feature; injection task rejected at API

### Playwright Tests
- [ ] v2 features settings shows injection disabled by default
- [ ] Enable injection requires authorization acknowledgment modal
- [ ] Injection events appear in security audit log UI
