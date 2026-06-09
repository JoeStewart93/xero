# Deployment Topology

## Local UI/BFF Stack

`platform/docker-compose.yml` runs the operator UI and local BFF stack.

```text
[ Operator Browser ]
        |
        v
[ Frontend container :3000 ]
        |
        v
[ BFF backend container :8000 ]
        |                  |
        v                  v
[ PostgreSQL ]        [ Redis ]
```

| Service | Image / build | Host port |
| :--- | :--- | :--- |
| postgres | `postgres:16` | internal only |
| redis | `redis:7` | internal only |
| backend | `platform/backend` with `XERO_SERVICE_ROLE=bff` | `${BACKEND_PORT:-8000}` |
| frontend | `platform/frontend` | `${FRONTEND_PORT:-3000}` |

## Separate C2 Backend Stack

`platform/docker-compose.c2.yml` runs the C2 backend independently. This stack can run on the same machine for local development or on a remote server.

```text
[ Xero UI Settings ]
        |
        | POST /api/v1/c2/connect
        v
[ C2 backend container :8000 ]
        |                  |
        v                  v
[ C2 PostgreSQL ]     [ C2 Redis ]
```

The C2 backend is the default embedded beacon handler and embedded scanner. It can accept beacon traffic directly and run scanner-backed recon workflows without requiring external handler or scanner infrastructure.

| Service | Image / build | Host port |
| :--- | :--- | :--- |
| c2-postgres | `postgres:16` | internal only |
| c2-redis | `redis:7` | internal only |
| c2-backend | `platform/backend` with `XERO_SERVICE_ROLE=c2` | `${C2_BACKEND_PORT:-8001}` |

## Optional External Infrastructure

Production-oriented deployments can add dedicated handler and scanner fleets while keeping the same C2 control plane.

```text
[ Operator Browser ]
        |
        v
[ Xero UI/BFF stack ]
        |
        v
[ Xero C2 Backend ]
        |                  |
        | handler control  | scanner control
        v                  v
[ Handler Pool ]      [ Scanner Pool ]
        |                  |
        v                  v
[ Beacons ]           [ Recon targets ]

Later pivot mode:
[ Xero C2 Backend ] -> [ Installed Beacon Pivot ] -> [ Internal scan/proxy target ]
```

| Role | Default | External mode | Feature |
| :--- | :--- | :--- | :--- |
| Beacon handler | Embedded in C2 backend | Dedicated external handlers registered to C2 | [F0038](../features/0038-connection-handler-binary.md), [F0039](../features/0039-handler-tunnel-to-core.md) |
| Handler failover | Direct C2 path remains available | Healthy handler assignment and beacon migration | [F0109](../features/0109-handler-load-balancing.md) |
| Scanner | Embedded in C2 backend | Dedicated scanner workers registered to C2 | [F0045](../features/0045-scanner-worker-registry.md) |
| Distributed scanning | Single embedded scanner job | Scan sharding across scanner workers with merged results | [F0046](../features/0046-distributed-scan-orchestration.md) |
| Pivot scanning/proxying | Not available by default | Installed beacon acts as scoped scanner/proxy vantage point | [F0047](../features/0047-beacon-pivot-scanning-and-proxying.md) |

## Healthchecks

| Endpoint | Auth | Purpose |
| :--- | :--- | :--- |
| `GET /health` | public | Container liveness |
| `GET /ready` | public | Container readiness, Postgres, Redis |
| `GET /api/v1/health` | operator JWT | UI/API liveness display |
| `GET /api/v1/ready` | operator JWT | UI/API readiness display |

## Environment

Secrets and local defaults are documented in `platform/.env.example`. Non-development deployments must override default JWT, operator, local admin, and C2 connection secrets.

Key role variables:

- `XERO_SERVICE_ROLE=bff|c2`
- `C2_CONNECT_PASSWORD`
- `C2_TOKEN_EXPIRES_MINUTES`
- `VITE_API_BASE_URL`
- `VITE_DEFAULT_C2_BASE_URL`

## CI/CD

GitHub Actions runs backend lint, OpenAPI drift checks, backend unit/behave tests, frontend lint/unit/build checks, Docker image builds, compose integration tests, and Playwright smoke tests on every PR. See [F0002](../features/0002-cicd-pipeline.md).

## Production Reference

| Component | Minimum |
| :--- | :--- |
| Xero C2 Backend | 4 vCPU, 8 GB RAM, SSD |
| PostgreSQL | Dedicated instance for production |
| Handler | <50 MB memory target |
| Scanner worker | Sized by scan concurrency and target scope |

## Later Production

- Kubernetes/Nginx load balancing templates for handler pools. ([F0109](../features/0109-handler-load-balancing.md))
- Scanner worker pools for distributed recon. ([F0045](../features/0045-scanner-worker-registry.md), [F0046](../features/0046-distributed-scan-orchestration.md))
- RabbitMQ alternative bus. ([F0110](../features/0110-rabbitmq-message-bus.md))
