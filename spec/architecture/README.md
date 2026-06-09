# Xero Architecture

Architecture reference for the Xero C2 platform. Feature-level implementation and test plans live in [`../features/`](../features/).

## Current Architecture Notes

- The local UI/BFF stack is deployed by `platform/docker-compose.yml`.
- The C2 backend stack is deployed separately by `platform/docker-compose.c2.yml`.
- The C2 backend is the embedded/default beacon handler and embedded/default scanner.
- External handler and scanner fleets, distributed scanning, and beacon pivot routes are planned infrastructure extensions.
- The UI authenticates to the local BFF first, then connects to a local or remote C2 backend from Settings.
- Root `/health` and `/ready` endpoints remain public for container healthchecks; UI-facing health is protected behind local operator auth.

## Documents

| Document | Description |
| :--- | :--- |
| [system-overview.md](system-overview.md) | Vision, goals, current UI/BFF/C2 topology, beacon paths, scanner paths |
| [components.md](components.md) | UI, BFF, C2 backend, handlers, scanners, pivot routes, beacons, data stores |
| [protocol-stack.md](protocol-stack.md) | Local operator auth, C2 connection auth, handler/scanner control planes, TLS, WebSocket, binary protocol |
| [data-model.md](data-model.md) | PostgreSQL entities and Redis patterns, including planned handler/scanner/pivot records |
| [deployment-topology.md](deployment-topology.md) | Docker Compose stacks, optional handler/scanner fleets, ports, CI/CD, sizing |
| [security-model.md](security-model.md) | Auth, C2 connection tokens, scanner/pivot scope controls, mTLS, cert pinning, authorized use |
| [directory-structure.md](directory-structure.md) | `platform/` layout and test conventions |

## Related Specs

- [overview.md](../overview.md) - PRD and functional requirements
- [mvp-requirements.md](../mvp-requirements.md) - MVP scope and decisions
- [features/README.md](../features/README.md) - Implementation backlog
