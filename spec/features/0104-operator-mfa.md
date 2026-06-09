# F0104: Operator MFA

## Metadata
| Field | Value |
|---|---|
| ID | F0104 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0003 |

## Summary
Multi-factor authentication for operator login using TOTP authenticator apps, backup codes, and optional WebAuthn hardware keys for Xero UI/BFF access.

## Requirements
- TOTP MFA via authenticator app (Google Authenticator, Authy)
- 10 single-use backup codes generated on MFA enrollment
- WebAuthn/FIDO2 support as optional second factor
- MFA required on login when enabled for operator account
- MFA enrollment and recovery flows in settings UI

## Stages

### Stage 1: TOTP enrollment
**Goal:** Generate TOTP secret and QR code for operator.
**Acceptance Criteria:**
- [ ] POST /auth/mfa/enroll returns QR code and backup codes
- [ ] TOTP secret stored encrypted in database
- [ ] Verify enrollment with valid TOTP code before enabling

### Stage 2: Login MFA challenge
**Goal:** Two-step login: password then TOTP.
**Acceptance Criteria:**
- [ ] Login step 1 returns mfa_required flag and challenge token
- [ ] Step 2 POST /auth/mfa/verify with TOTP completes login
- [ ] Backup code accepted once then invalidated

### Stage 3: WebAuthn support
**Goal:** Optional hardware key registration and auth.
**Acceptance Criteria:**
- [ ] WebAuthn register flow in settings
- [ ] Login accepts WebAuthn assertion as second factor
- [ ] Fallback to TOTP if WebAuthn unavailable

## Feature Acceptance Criteria

- [ ] Operator with MFA enabled cannot login without second factor
- [ ] Backup code works once for recovery login
- [ ] WebAuthn key registered and usable for login

## Test Plan

### Unit Tests
- [ ] test_totp_generate_and_verify
- [ ] test_backup_code_single_use
- [ ] test_mfa_required_on_login
- [ ] test_webauthn_register_and_assert
- [ ] test_mfa_skip_rejected

### System / Integration Tests
- [ ] Enroll MFA; login requires TOTP; valid TOTP grants JWT
- [ ] Use backup code; subsequent use of same code rejected
- [ ] WebAuthn login completes full auth flow

### Playwright Tests
- [ ] MFA enrollment flow shows QR code and backup codes
- [ ] Login with MFA shows TOTP input step after password
- [ ] Invalid TOTP shows error without granting access
