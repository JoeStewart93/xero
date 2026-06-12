# System Overview

**Xero** is a modular Command & Control (C2) platform for authorized cybersecurity research, defensive testing, and scoped red-team operations.

## Vision

Xero automates scanning, enumeration, and post-exploitation workflows through a decoupled architecture. The operator UI, local BFF, C2 backend, embedded infrastructure roles, external handler/scanner fleets, and beacons are logically separate so the operator console can run locally while C2 logic runs locally or remotely.

## Product Goals

- **Modularity:** Swap communication profiles and infrastructure roles without redeploying the full platform.
- **Scalability:** Scale to many beacons and recon jobs through embedded C2 defaults first, then external handler and scanner fleets.
- **Stealth:** Traffic shaping and encryption minimize network noise.
- **Resilience:** Handler nodes, scanner nodes, pivot routes, and remote C2 deployments maintain operations when individual endpoints fail.

## Current Services

| Service | Current responsibility | Compose stack |
| :--- | :--- | :--- |
| Xero UI | Operator web console | \docker-compose.bff.yml\ |
| Local Xero BFF | Bootstrap auth, protected BFF health, bootstrap user persistence | \docker-compose.bff.yml\ |
| Xero C2 Backend | C2 operator auth, operator realtime, completed beacon registration, completed heartbeat/offline state, embedded beacon handler/scanner defaults, infrastructure worker pairing/liveness, exploit management, payload generation, post-exploitation orchestration | \docker-compose.c2.yml\ |
| Beacon handler scaffold | Separate service home for future external handler work; health/readiness plus optional C2 worker pairing/heartbeat today | \docker-compose.handler.yml\ |
| Scanner scaffold | Separate service home for future scanner worker work; health/readiness plus optional C2 worker pairing/heartbeat today; bundles masscan, nmap, gobuster, ffuf, httpx, subfinder, whois, dig, tcpdump | \docker-compose.scanner.yml\ |
| PostgreSQL / Redis | Per-stack persistence, readiness, C2 operator events, exploit/payload cache, and future queues/cache | BFF and C2 stacks |
| External beacon handlers | Pairable worker nodes today; beacon tunnel/relay behavior planned | Handler service evolution |
| External scanner workers | Pairable worker nodes today; recon execution behavior planned | Scanner service evolution |
| Beacon pivot workers/proxies | Later beacon-hosted scan/proxy vantage points inside authorized scope | Planned pivot deployment |
| Exploit/Payload System | Multi-source exploit aggregation, multi-language payload generation, encoder/obfuscator pipeline, post-exploitation orchestration | C2 backend integration |

## Current Operator Flow

\\\	ext
Operator Browser
  -> Xero UI
  -> Local Xero BFF
  -> Local PostgreSQL / Redis

Settings and operator login (F0074):
Xero UI
  -> POST /api/v1/auth/login on Xero C2 Backend
  -> C2 operator JWT stored as session + connection context

Operator realtime:
Xero UI
  -> ws(s)://<c2-api>/ws/operator with C2 operator JWT
  -> Xero C2 Backend subscribes to Redis events:operator

C2 infrastructure:
Xero UI
  -> Settings / Infrastructure
  -> /api/v1/infrastructure/workers and pairing/provisioning APIs
  -> Handler/scanner scaffolds pair and heartbeat to C2

Recon workflow:
Xero UI
  -> Select recon module (masscan, nmap, whois, http_enum, etc.)
  -> Configure targets and arguments
  -> Submit task to C2 Backend
  -> C2 routes to embedded scanner or external scanner worker
  -> Scanner executes and streams results via WebSocket
  -> Results auto-create/update assets in inventory
  -> Operator views results in real-time
\\\

## Beacon Network Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded handler | Beacon -> TLS/WebSocket -> Xero C2 Backend embedded handler -> operator \/ws/operator\ -> Xero UI | P0 |
| External handler | Beacon -> external handler -> Xero C2 Backend -> operator \/ws/operator\ -> Xero UI | P1 |
| Handler pool | Beacon -> assigned healthy handler -> Xero C2 Backend; beacons migrate when a handler fails | P1 |
| Ad-hoc handler | Beacon A -> Beacon B acting as handler -> Xero C2 Backend -> operator \/ws/operator\ -> Xero UI | P2 |

## Scanner Execution Paths

| Path | Flow | Priority |
| :--- | :--- | :--- |
| Embedded scanner | Xero UI -> C2 Backend embedded scanner -> result aggregation -> Xero UI | P0 |
| Selected scanner | Xero UI -> C2 Backend -> selected external scanner worker -> result aggregation -> Xero UI | P1 |
| Distributed scanner pool | Xero UI -> C2 Backend -> multiple scanner workers process shards -> merged results -> Xero UI | P1 |
| Beacon pivot | Xero UI -> C2 Backend -> authorized beacon pivot worker/proxy -> scoped scan or proxy result -> Xero UI | P2 |
| Beacon-side recon | Xero UI -> C2 Backend -> beacon executes recon module (Python or staged binary) -> results to C2 -> Xero UI | P0 |

## Recon Module Architecture

### Scanner Service (F0069)

The scanner Docker image bundles all reconnaissance tools:

**System Tools:**
- masscan (fast port scanner)
- nmap (comprehensive network scanner)
- whois, dig, host (DNS/whois queries)
- tcpdump (packet capture)
- gobuster, ffuf (web enumeration)
- httpx, subfinder (HTTP/subdomain discovery)

**Python Libraries:**
- aiohttp, httpx (async HTTP)
- impacket (SMB/LDAP/NetBIOS)
- dnspython, dnslib (DNS)
- cryptography, pyopenssl (SSL/TLS)
- python-whois, shodan, censys (enrichment)
- beautifulsoup4, lxml (HTML parsing)

**Bundled Wordlists:**
- common-directories.txt (~1k entries)
- medium-directories.txt (~10k entries)
- large-directories.txt (~50k entries, optional download)
- subdomain-common.txt (~500 entries)
- api-endpoints.txt, user-agents.txt

### Recon Module Categories

**Network Recon (F0050-F0059):**
- F0050: Masscan - Ultra-fast port scanning
- F0051: Nmap - Full-featured with NSE scripts
- F0052: Whois - Domain registration intelligence
- F0053: HTTP/Web Enum - Directory brute-forcing, tech detection
- F0054: Shodan/Censys - External threat intelligence
- F0055: NetBIOS - Windows network discovery
- F0056: LLMNR/mDNS - Local network participant discovery
- F0057: SSL/TLS Analysis - Certificate inspection
- F0058: Banner Grabbing - Service version extraction
- F0059: Vulnerability Scanning - CVE matching via NVD API

**Cloud Recon (F0060-F0062):**
- F0060: AWS - S3 buckets, EC2, IAM
- F0061: Azure - Storage, AD, Key Vault
- F0062: GCP - GCS buckets, GCE instances

**Application Recon (F0063-F0064):**
- F0063: API Discovery - OpenAPI, GraphQL, REST
- F0064: JWT Analysis - Token decoding and weakness detection

**Advanced Recon (F0065-F0068):**
- F0065: Certificate Transparency - Historical cert discovery
- F0066: Passive DNS - VirusTotal/SecurityTrails
- F0067: GitHub/GitLab - Repository and secret scanning
- F0068: ICMP/Traceroute - Network topology mapping

### API Key Management (F0070)

External API keys (Shodan, Censys, VirusTotal, SecurityTrails) are:
- Stored encrypted in PostgreSQL (BCrypt)
- Overridable via environment variables
- Managed via C2 API endpoints
- Validated against provider APIs

### Asset Ingestion (F0071)

Recon results automatically create/update assets:
- Port scan -> Host assets
- Service enum -> Service assets (linked to hosts)
- Vuln scan -> Vulnerability assets (linked to services)
- DNS/Whois -> Domain assets
- Cloud recon -> Cloud resource assets

Deduplication by identifier (IP, domain, CVE) prevents duplicates.

### Beacon-Side Recon (F0073)

Beacons can execute recon from their vantage point:
- **Pure Python:** Memory-only, no external dependencies
- **Staged Binary:** Download tool to target, execute, cleanup
- **Hybrid:** Python wrapper with subprocess execution

Enables internal network scanning and pivoted recon.

## Related Features

- Foundation and operator realtime: [F0001](../features/0001-docker-compose-infrastructure.md)-[F0008](../features/0008-operator-websocket-realtime.md)
- Core C2: [F0009](../features/0009-beacon-registration.md)-[F0015](../features/0015-go-beacon-agent.md)
- Infrastructure worker pairing: [F0049](../features/0049-c2-infrastructure-worker-pairing.md)
- Handlers: [F0038](../features/0038-connection-handler-binary.md)-[F0044](../features/0044-adhoc-handler-installation.md), [F0109](../features/0109-handler-load-balancing.md)
- Scanner workers and distributed recon: [F0045](../features/0045-scanner-worker-registry.md)-[F0047](../features/0047-beacon-pivot-scanning-and-proxying.md)
- **Recon module expansion:** [F0050](../features/0050-masscan-fast-port-scanner.md)-[F0073](../features/0073-beacon-side-recon-execution.md)

See [overview.md](../overview.md) for the full PRD.
