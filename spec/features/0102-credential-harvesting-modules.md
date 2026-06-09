# F0102: Credential Harvesting Modules

## Metadata
| Field | Value |
|---|---|
| ID | F0102 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0016 |

## Summary
v2 post-exploitation modules for credential extraction from LSA secrets, browser password stores, and Windows Credential Manager on authorized engagement targets.

## Requirements
- Modules: lsa_secrets, browser_creds, credman_enum
- Results encrypted at rest with operator-specific key
- Output redacted in UI by default; reveal requires click
- Authorized engagement flag required before module dispatch
- No credential data in logs or telemetry

## Stages

### Stage 1: LSA secrets module
**Goal:** Extract LSA-stored credentials on Windows.
**Acceptance Criteria:**
- [ ] builtin.lsa_secrets module with elevation check
- [ ] Output schema: target, username, secret_type (redacted)
- [ ] Requires admin/SYSTEM context or impersonation

### Stage 2: Browser and credman
**Goal:** Browser password store and Credential Manager enum.
**Acceptance Criteria:**
- [ ] browser_creds supports Chrome and Firefox profile paths
- [ ] credman_enum lists stored generic and domain credentials
- [ ] Secrets never written to plaintext result without encryption

### Stage 3: Secure result handling
**Goal:** Encrypted storage and redacted UI display.
**Acceptance Criteria:**
- [ ] Results encrypted with operator public key before DB storage
- [ ] UI shows redacted preview; reveal button fetches decrypted view
- [ ] Credential results excluded from WebSocket broadcast

## Feature Acceptance Criteria

- [ ] LSA module returns expected lab credential entries
- [ ] UI never shows credentials without explicit reveal action
- [ ] Credential data absent from application logs

## Test Plan

### Unit Tests
- [ ] test_lsa_module_elevation_check
- [ ] test_browser_creds_output_encrypted
- [ ] test_result_redaction_in_api_default
- [ ] test_reveal_requires_operator_auth
- [ ] test_no_credentials_in_logs

### System / Integration Tests
- [ ] Dispatch lsa_secrets on lab VM; encrypted result stored
- [ ] Reveal credential in UI; decrypted value shown once
- [ ] Unauthorized engagement flag blocks module dispatch

### Playwright Tests
- [ ] Credential modules hidden until v2 engagement mode enabled
- [ ] Result panel shows redacted credentials by default
- [ ] Reveal button shows credential with confirmation dialog
