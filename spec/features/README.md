# Xero Feature Index

Numbered implementation backlog for Xero. Features are developed in order where practical; dependencies must be satisfied before starting a dependent feature.

**Template:** [_template.md](_template.md)

## Current Alignment Notes

- F0001-F0015, F0015.01-AMD, F0048, and F0049 are complete.
- The current UI/BFF stack, separate C2 stack, handler scaffold, and scanner scaffold are documented in F0001, F0048, and the architecture docs.
- The current UI navigation is Home, Projects, Recon, Beacons, Exploits, Payloads, Assets, Reports, Loot, Settings, and separated Health/Realtime utility surfaces. Several sections are routeable shell stubs only; Inventory is under Assets.
- F0008 adds direct-to-C2 operator realtime over /ws/operator; F0009 completes the beacon registration contract and the initial C2-backed Beacons overview; F0010 completes beacon heartbeat, stale/offline transitions, and active/offline UI counts.
- The C2 backend is the default embedded beacon handler and embedded scanner; F0049 adds shared worker pairing/liveness and Settings > Infrastructure inventory. Handler tunnels, scanner execution, distributed scan orchestration, and beacon pivot scanning/proxying remain planned features.
- **F0074 (planned):** Splits auth into BFF bootstrap (setup) and C2 operator (platform). C2 operator login replaces `C2_CONNECT_PASSWORD`; user management moves to C2. See [0074-c2-operator-authentication.md](0074-c2-operator-authentication.md).
- **Recon Module Expansion (F0050-F0073):** Comprehensive reconnaissance capabilities including masscan, nmap, whois, HTTP enumeration, Shodan/Censys enrichment, NetBIOS, LLMNR/mDNS, SSL/TLS analysis, banner grabbing, vulnerability scanning, cloud recon (AWS/Azure/GCP), API/JWT analysis, CT logs, passive DNS, GitHub/GitLab recon, and ICMP/traceroute. Includes scanner Docker image (F0069), API key management (F0070), asset ingestion (F0071), reporting (F0072), and beacon-side execution (F0073).
- **Exploit & Payload System (F0080-F0083):** Comprehensive exploit management with multi-source aggregation (Metasploit, ExploitDB, built-in), multi-language payload generation (Go, Python, PowerShell, Bash, Rust, C#), encoder/obfuscator pipeline, and post-exploitation orchestration. Supports exploit suggestions based on target profiles, chained execution workflows, and unified beacon deployment integration.\n
- **Rootkit Suite (F0200-F0207):** Comprehensive post-exploitation rootkit capabilities for Linux (LKM and eBPF) and Windows (DKOM/callbacks). Supports hiding processes, files, network connections, and memory; file/memory/process protection; multiple persistence mechanisms; configurable heartbeat communications; encrypted interactive shell over WebSocket; evasion protections with stealth sleep-mode; and dynamic build server for kernel version-specific compilation.\n
## Dependency Overview

\\\mermaid
flowchart TD
  subgraph phase1 [Phase 1 Foundation]
    F0001[F0001 Docker Compose]
    F0002[F0002 CI/CD]
    F0004[F0004 FastAPI]
    F0005[F0005 PostgreSQL]
    F0006[F0006 Redis]
    F0003[F0003 Auth]
    F0007[F0007 UI Shell]
    F0008[F0008 Operator Realtime]
    F0048[F0048 Service Boundaries]
    F0074[F0074 C2 Operator Auth]
  end
  subgraph phase2 [Phase 2 Core C2]
    F0009[F0009 Registration]
    F0011[F0011 Binary Protocol]
    F0014[F0014 Task Queue]
    F0015[F0015 Go Beacon]
    F001501[F0015.01 MinIO Artifacts]
  end
  subgraph phase3 [Phase 3 Tasking & Recon Foundation]
    F0016[F0016 Commands]
    F0022[F0022 Port Scan]
    F0023[F0023 Service Enum]
    F0024[F0024 Dashboard]
    F0069[F0069 Scanner Docker]
    F0070[F0070 API Keys]
  end
  subgraph phase4 [Phase 4 Recon Expansion]
    F0050[F0050 Masscan]
    F0051[F0051 Nmap]
    F0052[F0052 Whois]
    F0053[F0053 HTTP Enum]
    F0054[F0054 Shodan/Censys]
    F0055[F0055 NetBIOS]
    F0056[F0056 LLMNR/mDNS]
    F0057[F0057 SSL/TLS]
    F0058[F0058 Banner Grab]
    F0059[F0059 Vuln Scan]
    F0071[F0071 Asset Ingestion]
    F0073[F0073 Beacon Recon]
  end
  subgraph phase5 [Phase 5 Advanced Recon]
    F0060[F0060 AWS Recon]
    F0061[F0061 Azure Recon]
    F0062[F0062 GCP Recon]
    F0063[F0063 API Discovery]
    F0064[F0064 JWT Analysis]
    F0065[F0065 CT Logs]
    F0066[F0066 Passive DNS]
    F0067[F0067 GitHub Recon]
    F0068[F0068 ICMP/Traceroute]
    F0072[F0072 Reporting]
  end
  subgraph infra [Infrastructure]
    F0038[F0038 Handler Binary]
    F0039[F0039 Handler Tunnel]
    F0045[F0045 Scanner Registry]
    F0046[F0046 Distributed Scans]
    F0047[F0047 Beacon Pivot]
    F0049[F0049 Worker Pairing]
    F0109[F0109 Handler LB]
  end
  subgraph exploit [Exploits & Payloads]
    F0080[F0080 Exploit Mgmt]
    F0081[F0081 Payload Gen]
    F0082[F0082 Post-Exploit]
    F0083[F0083 Source Adapters]
  end
  F0001 --> F0002
  F0001 --> F0004
  F0004 --> F0005
  F0004 --> F0006
  F0048 --> F0074
  F0074 --> F0104
  F0074 --> F0105
  F0001 --> F0003
  F0003 --> F0007
  F0004 --> F0008
  F0006 --> F0008
  F0007 --> F0008
  F0004 --> F0009
  F0010 --> F0048
  F0048 --> F0011
  F0048 --> F0049
  F0049 --> F0045
  F0049 --> F0039
  F0009 --> F0015
  F0015 --> F001501
  F0014 --> F0016
  F001501 --> F0017
  F001501 --> F0029
  F001501 --> F0072
  F001501 --> F0073
  F001501 --> F0081
  F001501 --> F0107
  F001501 --> F0207
  F0016 --> F0022
  F0016 --> F0024
  F0022 --> F0023
  F0011 --> F0038
  F0038 --> F0039
  F0039 --> F0109
  F0045 --> F0046
  F0046 --> F0047

  # Recon dependencies
  F0022 --> F0050
  F0022 --> F0051
  F0045 --> F0069
  F0004 --> F0070
  F0069 --> F0050
  F0069 --> F0051
  F0037 --> F0052
  F0023 --> F0053
  F0023 --> F0054
  F0070 --> F0054
  F0035 --> F0055
  F0016 --> F0056
  F0023 --> F0057
  F0023 --> F0058
  F0023 --> F0059
  F0030 --> F0059
  F0016 --> F0060
  F0016 --> F0061
  F0016 --> F0062
  F0053 --> F0063
  F0053 --> F0064
  F0052 --> F0065
  F0057 --> F0065
  F0054 --> F0066
  F0022 --> F0068
  F0017 --> F0071
  F0030 --> F0071
  F0016 --> F0073
  F0047 --> F0073
  F0071 --> F0072

  # Exploit/Payload dependencies
  F0023 --> F0080
  F0030 --> F0080
  F0080 --> F0083
  F0015 --> F0081
  F0021 --> F0081
  F0080 --> F0082
  F0081 --> F0082
  F0082 --> F0102
  F0082 --> F0103
\\\

F0005 completes the shared PostgreSQL persistence foundation; F0009 completes the beacon registration table and opaque token material; F0010 completes beacon heartbeat profile fields and \eacon_events\, while session/task/asset/handler/plugin domain persistence remains with dependent feature specs.
F0006 completes the shared Redis foundation; F0008 completes operator WebSocket delivery through Redis pub/sub, and F0014 completes real per-beacon task queues.
F0049 completes shared handler/scanner worker pairing, heartbeat, stale detection, Settings > Infrastructure inventory, and local scaffold provisioning. Scanner modules use the embedded C2 scanner by default; scanner job eligibility/execution, distributed scan sharding, and beacon pivot execution are planned in F0045-F0047.
**Recon modules (F0050-F0073)** expand scanning capabilities with masscan, nmap, whois, HTTP enumeration, enrichment APIs, network protocols, cloud recon, and beacon-side execution. F0069 provides the scanner Docker image with all tools; F0070 manages external API keys; F0071 ingests results into assets; F0072 integrates with reporting; F0073 enables beacon-side recon.
**Exploit & Payload system (F0080-F0083)** provides multi-source exploit aggregation, multi-language payload generation, encoder/obfuscator pipeline, and post-exploitation orchestration. F0080 manages the exploit catalog and suggestions; F0081 generates payloads in Go, Python, PowerShell, Bash, Rust, C#; F0082 orchestrates chained execution; F0083 integrates Metasploit, ExploitDB, and custom sources.

## Phase 1 - Foundation (Weeks 1-2)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0001 | [Docker Compose Infrastructure](0001-docker-compose-infrastructure.md) | P0 | - |
| F0002 | [CI/CD Pipeline](0002-cicd-pipeline.md) | P0 | F0001 |
| F0004 | [FastAPI Backend Foundation](0004-fastapi-backend-foundation.md) | P0 | F0001 |
| F0005 | [PostgreSQL Persistence](0005-postgresql-persistence.md) | P0 | F0001, F0004 |
| F0006 | [Redis Message Bus](0006-redis-message-bus.md) | P0 | F0001, F0004 |
| F0003 | [Operator Authentication](0003-operator-authentication.md) | P0 | F0001 plus auth persistence scaffolding |
| F0007 | [React UI Shell](0007-react-ui-shell.md) | P0 | F0001, F0003 |
| F0048 | [Service Boundary Refactor](0048-service-boundary-refactor.md) | P0 | F0001-F0010 |
| F0074 | [C2 Operator Authentication](0074-c2-operator-authentication.md) | P1 | F0048, F0008, F0009 |
| F0049 | [C2 Infrastructure Worker Pairing](0049-c2-infrastructure-worker-pairing.md) | P1 | F0008, F0010, F0048 |

## Phase 2 - Core C2 (Weeks 3-4)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0008 | [Operator WebSocket Realtime](0008-operator-websocket-realtime.md) | P0 | F0004, F0006, F0007 |
| F0009 | [Beacon Registration](0009-beacon-registration.md) | P0 | F0004, F0005 |
| F0010 | [Beacon Heartbeat & Keepalive](0010-beacon-heartbeat-keepalive.md) | P0 | F0009 |
| F0011 | [Beacon Binary Protocol](0011-beacon-binary-protocol.md) | P0 | F0048 |
| F0012 | [Beacon WebSocket Transport](0012-beacon-websocket-transport.md) | P0 | F0009, F0011 |
| F0013 | [Beacon HTTP Long-poll Fallback](0013-beacon-http-longpoll-fallback.md) | P0 | F0009, F0011 |
| F0014 | [Task Queue](0014-task-queue.md) | P0 | F0006, F0009 |
| F0015 | [Go Beacon Agent](0015-go-beacon-agent.md) | P0 | F0011-F0014 |
| F0015.01-AMD | [MinIO Artifact Storage](0015.01-amd-minio-artifact-storage.md) | P0 Amendment | F0015, F0005, F0048 |

## Phase 3 - Tasking, Sessions, Scanning, UI (Weeks 5-6)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0016 | [Command Execution](0016-command-execution.md) | P0 | F0014, F0015 |
| F0017 | [Result Collection](0017-result-collection.md) | P0 | F0016, F0005, F0015.01-AMD |
| F0018 | [Interactive Shell Session](0018-interactive-shell-session.md) | P0 | F0016, F0017 |
| F0019 | [File Browser Session](0019-file-browser-session.md) | P0 | F0016, F0017 |
| F0020 | [Registry Editor Session](0020-registry-editor-session.md) | P0 | F0016, F0017 |
| F0021 | [Traffic Shaping Profiles](0021-traffic-shaping-profiles.md) | P0 | F0015, F0011 |
| F0022 | [Port Scanning Module](0022-port-scanning-module.md) | P0 | F0016 |
| F0023 | [Service Enumeration Module](0023-service-enumeration-module.md) | P0 | F0022 |
| F0024 | [Home Overview / Dashboard UI](0024-dashboard-ui.md) | P0 | F0007, F0008, F0009 |
| F0025 | [Beacon Management UI](0025-beacon-management-ui.md) | P0 | F0024, F0009 |
| F0026 | [Task Execution UI](0026-task-execution-ui.md) | P0 | F0024, F0016 |
| F0027 | [Realtime Results UI](0027-realtime-results-ui.md) | P0 | F0008, F0017 |
| F0028 | [Inventory / Module Browser UI](0028-module-browser-ui.md) | P0 | F0024, F0022 |
| F0069 | [Scanner Tool Docker Image](0069-scanner-tool-docker-image.md) | P0 | F0045 |
| F0070 | [External API Key Management](0070-external-api-key-management.md) | P0 | F0004 |

## Phase 4 - Recon Expansion (Weeks 7-8)

### P0 - Core Network Recon (MVP Critical)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0050 | [Masscan Fast Port Scanner](0050-masscan-fast-port-scanner.md) | P0 | F0022, F0045, F0069 |
| F0051 | [Nmap Wrapper with NSE Scripts](0051-nmap-wrapper-nse-scripts.md) | P0 | F0022, F0045, F0069 |
| F0052 | [Whois Domain Lookup](0052-whois-domain-lookup.md) | P0 | F0037, F0069 |
| F0053 | [HTTP/Web Enumeration](0053-http-web-enumeration.md) | P0 | F0016, F0023, F0069 |
| F0054 | [Shodan/Censys Enrichment](0054-shodan-censys-enrichment.md) | P0 | F0023, F0030, F0069, F0070 |
| F0055 | [NetBIOS Enumeration](0055-netbios-enumeration.md) | P0 | F0035, F0069 |
| F0056 | [LLMNR/mDNS Discovery](0056-llmnr-mdns-discovery.md) | P0 | F0016, F0069 |
| F0057 | [SSL/TLS Certificate Analysis](0057-ssl-tls-certificate-analysis.md) | P0 | F0023, F0069 |
| F0058 | [Extended Banner Grabbing](0058-extended-banner-grabbing.md) | P0 | F0023, F0069 |
| F0059 | [Vulnerability Scanning (Light)](0059-vulnerability-scanning-light.md) | P0 | F0023, F0030, F0069 |
| F0071 | [Recon Result to Asset Ingestion](0071-recon-result-asset-ingestion.md) | P0 | F0030, F0017 |
| F0073 | [Beacon-Side Recon Execution](0073-beacon-side-recon-execution.md) | P0 | F0016, F0047, F0015.01-AMD |

### P1 - Additional Recon (MVP Scope)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0060 | [AWS Cloud Recon](0060-aws-cloud-recon.md) | P1 | F0016, F0030, F0069 |
| F0061 | [Azure Cloud Recon](0061-azure-cloud-recon.md) | P1 | F0016, F0030, F0069 |
| F0062 | [GCP Cloud Recon](0062-gcp-cloud-recon.md) | P1 | F0016, F0030, F0069 |
| F0063 | [API Discovery & Enumeration](0063-api-discovery-enumeration.md) | P1 | F0053, F0069 |
| F0064 | [JWT Analysis](0064-jwt-analysis.md) | P1 | F0053, F0069 |
| F0065 | [Certificate Transparency Log Search](0065-certificate-transparency-logs.md) | P1 | F0052, F0057, F0069 |
| F0066 | [Passive DNS Enrichment](0066-passive-dns-enrichment.md) | P1 | F0054, F0069, F0070 |
| F0067 | [GitHub/GitLab Recon](0067-github-gitlab-recon.md) | P1 | F0016, F0069 |
| F0068 | [ICMP/Traceroute Mapping](0068-icmp-traceroute-mapping.md) | P1 | F0022, F0069 |
| F0072 | [Recon Reporting Integration](0072-recon-reporting-integration.md) | P1 | F0071, F0015.01-AMD |

## Phase 5 - Assets, Handlers, Plugins, Exploits & Payloads (Weeks 9-10)

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0029 | [File Transfer](0029-file-transfer.md) | P0 | F0016, F0015, F0015.01-AMD |
| F0030 | [Asset Inventory](0030-asset-inventory.md) | P1 | F0005, F0009 |
| F0031 | [Automatic Asset Grouping](0031-automatic-asset-grouping.md) | P1 | F0030 |
| F0032 | [Manual Asset Grouping](0032-manual-asset-grouping.md) | P1 | F0030 |
| F0033 | [Asset Management UI](0033-asset-management-ui.md) | P1 | F0030, F0032 |
| F0034 | [Network Topology View](0034-network-topology-view.md) | P1 | F0030, F0024 |
| F0035 | [SMB Enumeration](0035-smb-enumeration.md) | P1 | F0016 |
| F0036 | [LDAP Enumeration](0036-ldap-enumeration.md) | P1 | F0016 |
| F0037 | [DNS Enumeration](0037-dns-enumeration.md) | P1 | F0016 |
| F0038 | [Connection Handler Binary](0038-connection-handler-binary.md) | P1 | F0011, F0048 |
| F0039 | [Handler Tunnel to C2 Backend](0039-handler-tunnel-to-core.md) | P1 | F0038, F0049 |
| F0040 | [Handler Traffic Masking](0040-handler-traffic-masking.md) | P1 | F0038, F0021 |
| F0041 | [Plugin API](0041-plugin-api.md) | P1 | F0016, F0004 |
| F0042 | [Python Plugin Reference](0042-python-plugin-reference.md) | P1 | F0041 |
| F0043 | [Plugin Hot-reload](0043-plugin-hot-reload.md) | P2 | F0041, F0015 |
| F0044 | [Ad-hoc Handler Installation](0044-adhoc-handler-installation.md) | P2 | F0038, F0029, F0015 |
| F0045 | [Scanner Worker Registry](0045-scanner-worker-registry.md) | P1 | F0049 |
| F0046 | [Distributed Scan Orchestration](0046-distributed-scan-orchestration.md) | P1 | F0022, F0045, F0017 |
| F0047 | [Beacon Pivot Scanning and Proxying](0047-beacon-pivot-scanning-and-proxying.md) | P2 | F0015, F0016, F0046 |
| F0109 | [Handler Load Balancing](0109-handler-load-balancing.md) | P1 | F0038, F0039, F0010 |
| **Exploits & Payloads** | | | |
| F0080 | [Exploit Management System](0080-exploit-management-system.md) | P0 | F0023, F0030 |
| F0081 | [Payload Generation System](0081-payload-generation-system.md) | P0 | F0015, F0021, F0015.01-AMD |
| F0082 | [Post-Exploitation Orchestration](0082-post-exploitation-orchestration.md) | P1 | F0080, F0081 |
| F0083 | [Exploit Source Adapters](0083-exploit-source-adapters.md) | P1 | F0080 |

## Post-MVP v2

| ID | Feature | Priority | Depends |
| :--- | :--- | :--- | :--- |
| F0101 | [Process Injection & Token Impersonation](0101-process-injection-token-impersonation.md) | v2 | F0015 |
| F0102 | [Credential Harvesting Modules](0102-credential-harvesting-modules.md) | v2 | F0016 |
| F0103 | [Lateral Movement Modules](0103-lateral-movement-modules.md) | v2 | F0016, F0102 |
| F0104 | [Operator MFA](0104-operator-mfa.md) | v2 | F0074 |
| F0105 | [Multi-role RBAC](0105-multi-role-rbac.md) | v2 | F0074 |
| F0106 | [Plugin Marketplace](0106-plugin-marketplace.md) | v2 | F0041 |
| F0107 | [Additional Beacon Languages](0107-additional-beacon-languages.md) | v2 | F0011, F0015, F0015.01-AMD |
| F0108 | [Memory-only Beacon Execution](0108-memory-only-beacon-execution.md) | v2 | F0015 |
| F0110 | [RabbitMQ Message Bus](0110-rabbitmq-message-bus.md) | v2 | F0006 |
| F0200 | [Rootkit Suite Overview](0200-rootkit-suite-overview.md) | v2 | F0015, F0018, F0041 |
| F0201 | [Linux LKM Rootkit](0201-linux-lkm-rootkit.md) | v2 | F0015, F0200, F0207 |
| F0202 | [Linux eBPF Rootkit](0202-linux-ebpf-rootkit.md) | v2 | F0015, F0200, F0207 |
| F0203 | [Windows Rootkit](0203-windows-rootkit.md) | v2 | F0015, F0200 |
| F0204 | [Rootkit Persistence](0204-rootkit-persistence.md) | v2 | F0015, F0200, F0201, F0202, F0203 |
| F0205 | [Rootkit Communication](0205-rootkit-communication.md) | v2 | F0015, F0200, F0204 |
| F0206 | [Rootkit Evasion](0206-rootkit-evasion.md) | v2 | F0015, F0200, F0205 |
| F0207 | [Rootkit Build Server](0207-rootkit-build-server.md) | v2 | F0015, F0015.01-AMD, F0200, F0201, F0202 |
| F0220 | [Rootkit Discovery & Evasion](0220-rootkit-discovery-evasion.md) | High | F0200, F0201, F0202, F0203 |
| F0221 | [Credential Harvesting](0221-credential-harvesting.md) | High | F0015, F0200, F0203 |
| F0222 | [C2 Resilience & Redundancy](0222-c2-resilience.md) | High | F0200, F0205 |
| F0223 | [Advanced Process Injection](0223-process-injection.md) | Medium | F0015, F0200, F0203 |
| F0224 | [Time-Based Execution](0224-time-based-execution.md) | Medium | F0200, F0205 |
| F0225 | [Anti-Forensics](0225-anti-forensics.md) | Medium | F0200, F0203, F0204 |
| F0226 | [Module Signing](0226-module-signing.md) | High | F0200, F0201, F0203, F0207 |
| F0227 | [Container & Cloud Rootkit](0227-container-cloud-rootkit.md) | Low | F0200, F0202, F0203 |
| F0228 | [Resource Monitoring](0228-resource-monitoring.md) | Low | F0200, F0205 |
| F0229 | [Evasion Testing](0229-evasion-testing.md) | High | F0220, F0206 |

## Recon Module Summary

The Recon module expansion (F0050-F0073) provides comprehensive reconnaissance capabilities:

### Infrastructure
- **F0069:** Scanner Tool Docker Image - Bundles all recon tools (masscan, nmap, gobuster, etc.)
- **F0070:** External API Key Management - Manages Shodan, Censys, VirusTotal, SecurityTrails keys

### Core Network Recon (P0)
- **F0050:** Masscan - Ultra-fast port scanning for large networks
- **F0051:** Nmap - Full-featured scanning with NSE scripts
- **F0052:** Whois - Domain registration intelligence
- **F0053:** HTTP/Web Enum - Directory brute-forcing, tech detection, vhosts
- **F0054:** Shodan/Censys - External threat intelligence enrichment
- **F0055:** NetBIOS - Windows network discovery
- **F0056:** LLMNR/mDNS - Local network participant discovery
- **F0057:** SSL/TLS Analysis - Certificate inspection and vulnerability detection
- **F0058:** Banner Grabbing - Service version extraction
- **F0059:** Vulnerability Scanning - CVE matching via NVD API

### Cloud & Application Recon (P1)
- **F0060-F0062:** AWS/Azure/GCP Cloud Recon
- **F0063:** API Discovery - OpenAPI, GraphQL, REST enumeration
- **F0064:** JWT Analysis - Token decoding and weakness detection
- **F0065:** Certificate Transparency - Historical cert discovery
- **F0066:** Passive DNS - VirusTotal/SecurityTrails enrichment
- **F0067:** GitHub/GitLab - Repository and secret scanning
- **F0068:** ICMP/Traceroute - Network topology mapping

### Integration
- **F0071:** Asset Ingestion - Auto-create assets from scan results
- **F0072:** Reporting - Include recon data in reports
- **F0073:** Beacon Recon - Execute recon from compromised hosts

## Exploit & Payload System Summary

The Exploit & Payload System (F0080-F0083) provides comprehensive exploitation and payload generation capabilities:

### Core System
- **F0080:** Exploit Management System - Multi-source exploit catalog, suggestion engine, execution workflow
- **F0081:** Payload Generation System - Multi-language payload generators, encoder/obfuscator pipeline
- **F0082:** Post-Exploitation Orchestration - Chained execution workflows, module coordination
- **F0083:** Exploit Source Adapters - Metasploit, ExploitDB, and custom source integration

### Exploit Management (F0080)
- Unified exploit catalog with CVE metadata, affected services, references
- Exploit suggestion engine based on asset/service enumeration results
- Exploit execution workflow with payload binding
- Results tracking and correlation with assets

### Payload Generation (F0081)
- Multi-language support: Go, Python, PowerShell, Bash, Rust, C#
- Template-based payload configuration (stager, reverse shell, bind shell)
- Encoder/obfuscator pipeline (XOR, Base64, custom transformations)
- Traffic shaping profile integration
- Unified beacon deployment integration

### Post-Exploitation (F0082)
- Post-exploitation module registry
- Chained execution: exploit → payload → post-exploit modules
- Credential harvesting, lateral movement, persistence integration
- Results aggregation and loot correlation

### Source Adapters (F0083)
- Metasploit RPC adapter
- ExploitDB API adapter
- Custom exploit import (local files, Git repos)
- Unified exploit schema normalization
- Source synchronization and caching

## Rootkit Suite Summary

The Rootkit Suite (F0200-F0207) provides comprehensive post-exploitation stealth and persistence capabilities:

### Overview
- **F0200:** Rootkit Suite Overview - Architecture and coordination for all rootkit features

### Platform-Specific Rootkits
- **F0201:** Linux LKM Rootkit - Loadable Kernel Module for Linux 4.x-6.x
- **F0202:** Linux eBPF Rootkit - eBPF-based rootkit for Linux 5.x+ (safer alternative)
- **F0203:** Windows Rootkit - DKOM/callback-based rootkit for Windows 10/11

### Core Capabilities
- **F0204:** Rootkit Persistence - Init scripts, systemd, registry, scheduled tasks, services
- **F0205:** Rootkit Communication - Heartbeat, WebSocket shell, DNS/ICMP tunneling, traffic masking
- **F0206:** Rootkit Evasion - AV/EDR detection, anti-debugging, code obfuscation, process masquerading

### Build Infrastructure
- **F0207:** Rootkit Build Server - Dynamic compilation for target kernel versions

### Hiding Capabilities
- Process hiding from ps, top, Task Manager, Process Explorer
- File hiding from ls, find, Explorer, dir
- Network hiding from ss, netstat, Get-NetTCPConnection
- Memory hiding from debuggers and memory scanners

### Protection Capabilities
- File locking to prevent unauthorized access
- Memory locking to prevent debugger reads
- Process protection to prevent termination

### Communication Features
- Configurable heartbeat (1 second to 24 hours)
- Multiple transport: WebSocket, HTTP, DNS, ICMP
- Encrypted shell over WebSocket (AES-256-GCM)
- Traffic masking and CDN mimicry

### Evasion Features
- AV/EDR scan detection and response
- Anti-debugging techniques
- Code obfuscation and encryption
- VM/sandbox detection
- Stealth sleep-mode with port knocker wake

## Testing Requirements

Every feature spec includes:

1. **Unit tests** - isolated module/function coverage.
2. **System/integration tests** - Docker Compose and API/beacon flows.
3. **Playwright tests** - operator-visible UI validation.

A feature is **Complete** only when all stage acceptance criteria, feature acceptance criteria, and test plan items pass in CI.
