# Security Model

## Authorized Use

Xero is for **authorized cybersecurity research, defensive security testing, and scoped red-team operations** only. Operators must have written permission before deploying beacons, handlers, scanners, or pivot routes. See [mvp-requirements.md](../mvp-requirements.md#10-authorized-use).

## Encryption in Transit (SR-01)

| Path | Mechanism |
| :--- | :--- |
| Operator -> UI | HTTPS/TLS in deployed environments |
| UI -> Local BFF | HTTPS/TLS in deployed environments + local operator JWT |
| UI -> C2 Backend | HTTPS/TLS in deployed environments + C2 connection token |
| Beacon -> C2/Handler | TLS 1.3 |
| Handler -> C2 Backend | Encrypted tunnel + cert pinning (SR-03) |
| Scanner worker -> C2 Backend | HTTPS/TLS in deployed environments + planned scanner worker token/certificate |
| Beacon pivot -> C2 Backend | Beacon transport security plus scoped task authorization |

## Authentication

| Actor | Method | Feature |
| :--- | :--- | :--- |
| Local operator | Username/password + JWT | [F0003](../features/0003-operator-authentication.md) |
| Local administrator | Default development seed `admin/admin`, DB-backed, enabled by default | [F0003](../features/0003-operator-authentication.md) |
| UI -> C2 Backend | C2 connection password exchanged for C2 token | [F0001](../features/0001-docker-compose-infrastructure.md), [F0004](../features/0004-fastapi-backend-foundation.md) |
| Beacon registration | C2-role registration returns an opaque per-beacon token once and stores only a SHA-256 hash | [F0009](../features/0009-beacon-registration.md) |
| Operator MFA | TOTP/WebAuthn | [F0104](../features/0104-operator-mfa.md) (v2) |
| Beacon -> Handler | Mutual TLS (mTLS) | [F0038](../features/0038-connection-handler-binary.md) |
| External handler -> C2 Backend | Planned handler registration credential plus pinned tunnel | [F0039](../features/0039-handler-tunnel-to-core.md) |
| External scanner -> C2 Backend | Planned scanner registration credential plus capability-scoped worker token | [F0045](../features/0045-scanner-worker-registry.md) |
| Beacon pivot worker/proxy | Existing beacon identity plus explicit pivot job authorization | [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |

**Note:** Beacon mTLS is distinct from operator MFA.

## Public and Protected Health

| Endpoint | Auth | Purpose |
| :--- | :--- | :--- |
| `GET /health` | Public | Container liveness |
| `GET /ready` | Public | Container readiness for Postgres/Redis |
| `GET /api/v1/health` | Local operator JWT | Authenticated UI/API health |
| `GET /api/v1/ready` | Local operator JWT | Authenticated UI/API readiness |

The frontend `/health` page is protected and requires local operator login.

## Authorization

- MVP: local operator/admin roles stored on the `users` table.
- Admin disablement and richer user management are planned follow-up work.
- v2: multi-role RBAC. ([F0105](../features/0105-multi-role-rbac.md))

## Secrets (SR-02)

Database credentials, JWT secrets, local operator/admin seed credentials, and C2 connection secrets come from environment variables or Vault. Never commit production secrets.

Development defaults include:

- `OPERATOR_USERNAME=operator`
- `OPERATOR_PASSWORD=operator_password`
- `LOCAL_ADMIN_USERNAME=admin`
- `LOCAL_ADMIN_PASSWORD=admin`
- `JWT_SECRET_KEY=dev-only-xero-jwt-secret-change-me`
- `C2_CONNECT_PASSWORD=c2_password`

Non-development modes must override default JWT, operator, local admin, and C2 connection values.

## Traffic Stealth (SR-04)

Traffic shaping profiles mimic legitimate services. See [F0021](../features/0021-traffic-shaping-profiles.md).

## Recon Scope Controls

- Embedded and external scanners must enforce active project scope before dispatching scan jobs.
- Distributed scan shards retain project, scanner, target, operator, and parent job identifiers for audit.
- Pivot scanning/proxying must require explicit operator action and record the beacon pivot route used for each job.
- External scanners and pivot routes must not expand authorized scope automatically; they only provide execution vantage points for already-approved targets.

## Payload Security

- F0009 provides opaque registration token material and stores only token hashes.
- AES-256-GCM payload encryption, HMAC-SHA256 message authentication, and RSA-4096 or ECC key exchange are owned by F0011.

See [protocol-stack.md](protocol-stack.md).

## Certificate Pinning

Handlers verify Xero C2 identity before tunnel establishment (SR-03). See [F0039](../features/0039-handler-tunnel-to-core.md).
