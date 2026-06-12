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
    |-- docker-compose.bff.yml
    |-- docker-compose.c2.yml
    |-- docker-compose.handler.yml
    |-- docker-compose.scanner.yml
    |-- .env.example
    |-- pyproject.toml
    |-- pytest.ini
    |-- common/
    |   `-- python/
    |       `-- xero_common/
    |-- services/
    |   |-- bff-api/
    |   |   |-- xero_bff/
    |   |   |-- alembic/
    |   |   |-- Dockerfile
    |   |   |-- requirements.txt
    |   |   `-- requirements-dev.txt
    |   |-- c2-api/
    |   |   |-- xero_c2/
    |   |   |-- alembic/
    |   |   |-- Dockerfile
    |   |   |-- requirements.txt
    |   |   `-- requirements-dev.txt
    |   |-- beacon-handler/
    |   |   |-- xero_beacon_handler/
    |   |   |-- Dockerfile
    |   |   `-- requirements.txt
    |   `-- scanner/
    |       |-- xero_scanner/
    |       |-- Dockerfile
    |       `-- requirements.txt
    |-- docs/
    |   `-- api/
    |       |-- bff.openapi.yaml
    |       |-- c2.openapi.yaml
    |       |-- beacon-handler.openapi.yaml
    |       `-- scanner.openapi.yaml
    |-- tests/
    |   |-- unit/
    |   `-- integration/
    |-- features/
    |-- scripts/
    |   |-- ci.py
    |   `-- openapi.py
    `-- frontend/
        |-- src/
        |-- e2e/
        |-- public/
        |-- Dockerfile
        |-- package.json
        |-- playwright.config.ts
        `-- vite.config.ts
```

## Compose Files

| File | Purpose |
| :--- | :--- |
| `platform/docker-compose.bff.yml` | Canonical local UI/BFF stack: frontend, BFF API, BFF Postgres, BFF Redis |
| `platform/docker-compose.yml` | Temporary compatibility alias for the BFF stack |
| `platform/docker-compose.c2.yml` | Separate C2 API stack: C2 API, C2 Postgres, C2 Redis |
| `platform/docker-compose.handler.yml` | External beacon handler scaffold with optional C2 worker pairing/heartbeat |
| `platform/docker-compose.scanner.yml` | External scanner scaffold with optional C2 worker pairing/heartbeat |

## API Specs

| Service | OpenAPI |
| :--- | :--- |
| BFF API | `platform/docs/api/bff.openapi.yaml` |
| C2 API | `platform/docs/api/c2.openapi.yaml` |
| Beacon handler scaffold | `platform/docs/api/beacon-handler.openapi.yaml` |
| Scanner scaffold | `platform/docs/api/scanner.openapi.yaml` |

## Test Conventions

| Type | Location | Runner |
| :--- | :--- | :--- |
| Backend/service unit | `platform/tests/unit/` | pytest |
| Backend/service integration | `platform/tests/integration/` | pytest + docker compose |
| Backend BDD | `platform/features/` | behave |
| Frontend unit | `platform/frontend/src/**/*.test.tsx` | vitest |
| Beacon unit | `platform/beacons/go/.../*_test.go` | go test, planned |
| E2E / Playwright | `platform/frontend/e2e/` | Playwright |
| CI orchestration | `.github/workflows/ci.yml` | GitHub Actions ([F0002](../features/0002-cicd-pipeline.md)) |

Every feature spec in `spec/features/` defines required unit, integration, and Playwright tests. Tests must pass before a feature is marked Complete.

## Naming

- Platform: **Xero**
- API prefix: `/api/v1`
- Local BFF package: `xero_bff`
- C2 API package: `xero_c2`
- Beacon handler scaffold package: `xero_beacon_handler`
- Scanner scaffold package: `xero_scanner`
- Shared Python package: `xero_common`
- C# beacon project, when implemented: `XeroBeacon.csproj`

## UI Development Requirement

Stitch MCP is a hard requirement and must be used first for UI development, redesign, restyling, or UI planning work. See [agent-instructions.md](../../agent-instructions.md).
