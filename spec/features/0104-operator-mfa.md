# F0104: Operator MFA

## Metadata
| Field | Value |
|---|---|
| ID | F0104 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0074 |

## Summary
Multi-factor authentication for C2 operator login using TOTP authenticator apps, backup codes, and optional WebAuthn hardware keys. MFA applies to C2 platform operators, not BFF bootstrap admin accounts used for first-run C2 URL configuration.

## Requirements
- TOTP MFA via authenticator app (Google Authenticator, Authy) on C2 operator login
- 10 single-use backup codes generated on MFA enrollment
- WebAuthn/FIDO2 support as optional second factor
- MFA required on login when enabled for a C2 operator account
- MFA enrollment and recovery flows in Settings UI (requires C2 operator session)
- BFF bootstrap admin exempt from MFA (break-glass local setup only)
- MFA secrets stored on C2 (`operators` table or related C2 tables)

## Stages

### Stage 1: TOTP enrollment
**Goal:** Generate TOTP secret and QR code for C2 operator.
**Acceptance Criteria:**
- [ ] POST /api/v1/auth/mfa/enroll returns QR code and backup codes
- [ ] TOTP secret stored encrypted in C2 database
- [ ] Verify enrollment with valid TOTP code before enabling

### Stage 2: Login MFA challenge
**Goal:** Two-step C2 login: password then TOTP.
**Acceptance Criteria:**
- [ ] C2 login step 1 returns mfa_required flag and challenge token
- [ ] Step 2 POST /api/v1/auth/mfa/verify with TOTP completes login
- [ ] Backup code accepted once then invalidated

### Stage 3: WebAuthn support
**Goal:** Optional hardware key registration and auth.
**Acceptance Criteria:**
- [ ] WebAuthn register flow in Settings (C2 operator session required)
- [ ] C2 login accepts WebAuthn assertion as second factor
- [ ] Fallback to TOTP if WebAuthn unavailable

## Feature Acceptance Criteria

- [ ] C2 operator with MFA enabled cannot login without second factor
- [ ] Backup code works once for recovery login
- [ ] WebAuthn key registered and usable for C2 login
- [ ] BFF bootstrap admin login remains single-factor

## Test Plan

### Unit Tests
- [ ] test_totp_generate_and_verify
- [ ] test_backup_code_single_use
- [ ] test_mfa_required_on_c2_login
- [ ] test_webauthn_register_and_assert
- [ ] test_mfa_skip_rejected
- [ ] test_bootstrap_admin_exempt_from_mfa

### System / Integration Tests
- [ ] Enroll MFA on C2; login requires TOTP; valid TOTP grants operator JWT
- [ ] Use backup code; subsequent use of same code rejected
- [ ] WebAuthn login completes full C2 auth flow

### Playwright Tests
- [ ] MFA enrollment flow shows QR code and backup codes
- [ ] C2 login with MFA shows TOTP input step after password
- [ ] Invalid TOTP shows error without granting access
