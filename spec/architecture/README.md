# Xero Architecture

Architecture reference for the Xero C2 platform. Feature-level implementation and test plans live in [`../features/`](../features/).

## Current Architecture Notes

- The local UI/BFF stack is deployed by `platform/docker-compose.bff.yml`; `platform/docker-compose.yml` is a temporary compatibility alias.
- The C2 backend stack is deployed separately by `platform/docker-compose.c2.yml`.
- The beacon handler and scanner scaffolds are deployed by `platform/docker-compose.handler.yml` and `platform/docker-compose.scanner.yml`.
- The C2 backend is the embedded/default beacon handler and embedded/default scanner.
- External handler and scanner fleets, distributed scanning, and beacon pivot routes are planned infrastructure extensions.
- The UI uses a dual auth model ([F0074](../features/0074-c2-operator-authentication.md)): bootstrap login to the BFF for setup, C2 operator login for platform access.
- Root `/health` and `/ready` endpoints remain public for container healthchecks; UI-facing BFF health is protected behind bootstrap auth; operational pages require a C2 operator session.

## Auth Model

| Feature | Scope |
| :--- | :--- |
| [F0003](../features/0003-operator-authentication.md) | BFF bootstrap authentication (delivered) |
| [F0074](../features/0074-c2-operator-authentication.md) | C2 operator authentication and unified login (planned) |
| [F0104](../features/0104-operator-mfa.md) | C2 operator MFA (v2) |
| [F0105](../features/0105-multi-role-rbac.md) | C2 RBAC and user management UI (v2) |

## Documents

| Document | Description |
| :--- | :--- |
| [system-overview.md](system-overview.md) | Vision, goals, current UI/BFF/C2 topology, beacon paths, scanner paths |
| [components.md](components.md) | UI, BFF, C2 backend, handlers, scanners, pivot routes, beacons, data stores |
| [protocol-stack.md](protocol-stack.md) | Bootstrap auth, C2 operator auth, handler/scanner control planes, TLS, WebSocket, binary protocol |
| [data-model.md](data-model.md) | PostgreSQL entities and Redis patterns, including planned handler/scanner/pivot records |
| [deployment-topology.md](deployment-topology.md) | Docker Compose stacks, optional handler/scanner fleets, ports, CI/CD, sizing |
| [security-model.md](security-model.md) | Auth, C2 operator tokens, scanner/pivot scope controls, mTLS, cert pinning, authorized use |
| [directory-structure.md](directory-structure.md) | `platform/` layout and test conventions |

## Related Specs

- [overview.md](../overview.md) - PRD and functional requirements
- [mvp-requirements.md](../mvp-requirements.md) - MVP scope and decisions
- [features/README.md](../features/README.md) - Implementation backlog
