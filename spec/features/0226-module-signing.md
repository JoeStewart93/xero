# F0226: Module Signing

## Metadata
| Field | Value |
|---|---|
| ID | F0226 |
| Priority | High |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0201, F0203, F0207 |

## Summary
Sign rootkit modules for production deployment including test signing, EV certificate signing, attestation signing, and Secure Boot compatibility.

## Windows Module Signing

### Test Signing
```powershell
# Enable test mode
bcdedit /set testsigning on

# Generate self-signed certificate
MakeCert -r -pe -n "CN=Xero Rootkit" -sky signature -ss my -sr %USERPROFILE%\Certificates xero.pfx

# Sign driver
signtool sign /fd SHA256 /f xero.pfx /t http://timestamp.digicert.com driver.sys
```

### EV Certificate Signing
```powershell
# Import EV certificate
Import-PfxCertificate -FilePath ev_cert.pfx -CertStoreLocation Cert:\LocalMachine\My

# Sign with EV certificate
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /as driver.sys
```

## Linux Module Signing

### MOK Enrollment
```bash
# Generate key pair
openssl genrsa -out MOK.key 2048
openssl req -new -key MOK.key -out MOK.crt -subj "/CN=Xero Rootkit/"

# Enroll MOK
/usr/bin/mokutil --add-key MOK.key
/usr/bin/mokutil --signup MOK.crt
```

### Sign Module
```bash
# Sign with MOK
openssl x509 -outform DER -in MOK.crt -out MOK.der
certsign --cert MOK.der --key MOK.key rootkit.ko
```

## Build Server Integration

```json
{
  "signing": {
    "windows": {
      "certificate_path": "certs/ev_cert.pfx",
      "certificate_password": "encrypted_password",
      "timestamp_server": "http://timestamp.digicert.com",
      "attestation": false
    },
    "linux": {
      "mok_key_path": "certs/MOK.key",
      "mok_cert_path": "certs/MOK.crt",
      "secure_boot": true
    }
  }
}
```

## Stages

### Stage 1: Windows Test Signing
- [ ] Self-signed certificate generation
- [ ] Test mode enablement
- [ ] Driver signing workflow

### Stage 2: Windows EV Signing
- [ ] EV certificate integration
- [ ] Timestamp server configuration
- [ ] Attestation signing setup

### Stage 3: Linux Signing
- [ ] MOK key generation and enrollment
- [ ] Module signing workflow
- [ ] Secure Boot compatibility

### Stage 4: Build Server Integration
- [ ] Automated signing in build process
- [ ] Certificate management
- [ ] Signature verification

## Feature Acceptance Criteria
- [ ] Windows driver loads in test mode
- [ ] EV signed driver loads in production
- [ ] Linux module loads with Secure Boot
- [ ] Signatures verified on load

## Test Plan

### Unit Tests
- [ ] test_certificate_generation
- [ ] test_signature_verification
- [ ] test_timestamp_inclusion

### System Tests
- [ ] Sign and load Windows driver
- [ ] Sign and load Linux module
- [ ] Verify with signtool/certutil

### Playwright Tests
- [ ] Configure signing in build UI
- [ ] Upload certificates
- [ ] View signing status
