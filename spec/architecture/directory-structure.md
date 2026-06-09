# Directory Structure

## Repository Layout

```text
xero/
|-- agent-instructions.md
|-- README.md
|-- .github/
|   `-- workflows/
|       `-- ci.yml
|-- docs/
|   `-- ci.md
|-- scripts/
|   `-- generate_feature_specs.py
|-- spec/
|   |-- overview.md
|   |-- mvp-requirements.md
|   |-- architecture/
|   `-- features/
`-- platform/
    |-- docker-compose.yml
    |-- docker-compose.c2.yml
    |-- .env.example
    |-- pyproject.toml
    |-- pytest.ini
    |-- scripts/
    |   |-- ci.py
    |   `-- openapi.py
    |-- docs/
    |   `-- api/
    |       `-- openapi.yaml
    |-- backend/
    |   |-- app/
    |   |-- alembic/
    |   |-- tests/
    |   |   |-- unit/
    |   |   `-- integration/
    |   |-- features/
    |   |-- Dockerfile
    |   |-- requirements.txt
    |   `-- requirements-dev.txt
    `-- frontend/
        |-- src/
        |   |-- components/
        |   |-- pages/
        |   `-- test/
        |-- e2e/
        |-- public/
        |   `-- assets/
        |-- Dockerfile
        |-- package.json
        |-- playwright.config.ts
        `-- vite.config.ts
```

## Compose Files

| File | Purpose |
| :--- | :--- |
| `platform/docker-compose.yml` | Local UI/BFF stack: frontend, BFF backend, Postgres, Redis |
| `platform/docker-compose.c2.yml` | Separate C2 backend stack: C2 backend, C2 Postgres, C2 Redis |

## Test Conventions

| Type | Location | Runner |
| :--- | :--- | :--- |
| Backend unit | `platform/backend/tests/unit/` | pytest |
| Backend integration | `platform/backend/tests/integration/` | pytest + docker compose |
| Backend BDD | `platform/backend/features/` | behave |
| Frontend unit | `platform/frontend/src/**/*.test.tsx` | vitest |
| Beacon unit | `platform/beacons/go/.../*_test.go` | go test, planned |
| E2E / Playwright | `platform/frontend/e2e/` | Playwright |
| CI orchestration | `.github/workflows/ci.yml` | GitHub Actions ([F0002](../features/0002-cicd-pipeline.md)) |

Every feature spec in `spec/features/` defines required unit, integration, and Playwright tests. Tests must pass before a feature is marked Complete.

## Naming

- Platform: **Xero**
- API prefix: `/api/v1`
- Local BFF role: `XERO_SERVICE_ROLE=bff`
- C2 backend role: `XERO_SERVICE_ROLE=c2`
- C# beacon project, when implemented: `XeroBeacon.csproj`

## UI Development Requirement

Stitch MCP is a hard requirement and must be used first for UI development, redesign, restyling, or UI planning work. See [agent-instructions.md](../../agent-instructions.md).
