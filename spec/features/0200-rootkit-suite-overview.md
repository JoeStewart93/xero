# F0200: Rootkit Suite Overview

## Metadata
| Field | Value |
|---|---|
| ID | F0200 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0018, F0041 |

## Summary
Comprehensive rootkit suite providing post-exploitation persistence and stealth capabilities for Linux (LKM and eBPF) and Windows (DKOM and eBPF via BPF-for-Windows). Supports hiding files, processes, memory, and network traffic; locking files and memory from debuggers; preventing process termination; multiple persistence mechanisms; configurable heartbeat communications; encrypted interactive shell over WebSocket; evasion protections with stealth sleep-mode; and traffic masking for firewall/WAF evasion.

## Rootkit Sub-Features

This overview feature coordinates the following sub-features:

| ID | Feature | Platform | Type |
| :--- | :--- | :--- | :--- |
| F0201 | [Linux LKM Rootkit](0201-linux-lkm-rootkit.md) | Linux | Loadable Kernel Module |
| F0202 | [Linux eBPF Rootkit](0202-linux-ebpf-rootkit.md) | Linux | eBPF Programs |
| F0203 | [Windows Rootkit](0203-windows-rootkit.md) | Windows | DKOM/SSDT/eBPF |
| F0204 | [Rootkit Persistence](0204-rootkit-persistence.md) | Multi | Init/Systemd/Registry |
| F0205 | [Rootkit Communication](0205-rootkit-communication.md) | Multi | Heartbeat/WebSocket |
| F0206 | [Rootkit Evasion](0206-rootkit-evasion.md) | Multi | Stealth/Traffic Masking |
| F0207 | [Rootkit Build Server](0207-rootkit-build-server.md) | Multi | Dynamic Compilation |

## Core Capabilities

### Hiding Capabilities
- **Process Hiding:** Remove processes from `/proc`, `ps`, `tasklist`, and kernel process lists
- **File Hiding:** Hide files from directory listings, `/proc`, and file system APIs
- **Network Hiding:** Conceal network connections, sockets, and routing table entries
- **Memory Hiding:** Mask memory regions from debuggers and memory scanners

### Protection Capabilities
- **File Locking:** Prevent file reads/writes/deletes by unauthorized processes
- **Memory Locking:** Lock memory pages to prevent debugger reads (mprotect/VirtualLock)
- **Process Protection:** Prevent termination of protected processes (kill signal interception)

### Communication Features
- **Configurable Heartbeat:** Adjustable intervals (seconds to hours) with jitter
- **Multiple Transport:** WebSocket, HTTP long-poll, DNS tunneling, ICMP covert channel
- **Encrypted Shell:** Proprietary binary protocol over WebSocket with AES-256-GCM
- **Traffic Masking:** Spoof user-agents, mimic CDN traffic, HTTP/2 multiplexing

### Evasion Protections
- **Stealth Sleep-Mode:** Minimize activity until wake signal received
- **Port Knocker Sequence:** Wake on specific port knock pattern
- **On-Demand Activation:** Respond only to C2 query, not periodic heartbeat
- **AV/EDR Evasion:** Sleep during scan detection, code obfuscation, anti-debugging

## Architecture Overview

```text
+-----------------------------------------------------------------+
|                      XERO C2 PLATFORM                            |
|  +---------------+  +---------------+  +-------------------+     |
|  | Rootkit UI    |  | Build Server  |  | Encrypted Shell   |     |
|  | Configuration |  | (F0207)       |  | WebSocket         |     |
|  +-------+-------+  +-------+-------+  +----------+--------+     |
+----------|---------------------|---------------------+-----------+
           |                     |                       |
           |  Configured         |  Compiled             |  Encrypted
           |  Rootkit            |  Payload              |  Binary Protocol
           v                     v                       v
+-----------------------------------------------------------------+
|                    ROOTKIT PAYLOAD                               |
|  +----------------------------------------------------------+   |
|  |              Common Rootkit Core                          |   |
|  |  - Heartbeat Manager (F0205)                              |   |
|  |  - Evasion Engine (F0206)                                 |   |
|  |  - Communication Layer (F0205)                            |   |
|  +---------------------------+--------------------------------+   |
|                              |                                    |
|  +---------------------------+--------------------------------+   |
|  |      Platform-Specific Rootkit Layer                        |   |
|  |  +--------------+  +--------------+  +--------------+       |   |
|  |  | Linux LKM    |  | Linux eBPF   |  | Windows      |       |   |
|  |  | (F0201)      |  | (F0202)      |  | (F0203)      |       |   |
|  |  +--------------+  +--------------+  +--------------+       |   |
|  +---------------------------+--------------------------------+   |
|                              |                                    |
|  +---------------------------+--------------------------------+   |
|  |              Persistence Layer (F0204)                       |   |
|  |  - Init Scripts / Systemd / Registry / Services              |   |
|  +--------------------------------------------------------------+   |
+---------------------------------------------------------------------+
           |
           v
+-----------------------------------------------------------------+
|                    TARGET SYSTEM                                 |
|  +-------------+  +-------------+  +---------------------+       |
|  |   Linux     |  |   Linux     |  |     Windows         |       |
|  |   Kernel    |  |   eBPF VM   |  |   Kernel/SSDT       |       |
|  +-------------+  +-------------+  +---------------------+       |
+-----------------------------------------------------------------+
```

## UI Configuration Workflow

1. **Rootkit Builder Page** (`/payloads/rootkits`)
   - Select target platform (Linux/Windows)
   - Select rootkit type (LKM/eBPF/DKOM)
   - Configure hiding capabilities (processes, files, network, memory)
   - Configure protection capabilities (file lock, memory lock, process protect)
   - Configure persistence (init/systemd/registry/service)
   - Configure communication (heartbeat interval, transport, encryption)
   - Configure evasion (sleep-mode, port knocker, traffic masking)
   - Generate payload (triggers F0207 build server for Linux)

2. **Rootkit Management Page** (`/beacons/rootkits`)
   - View active rootkits per beacon
   - Enable/disable hiding capabilities remotely
   - Toggle stealth mode
   - Trigger wake sequence
   - View rootkit status and logs

3. **Encrypted Shell Session** (`/sessions/shell/{id}`)
   - Interactive shell over encrypted WebSocket
   - Proprietary binary protocol with AES-256-GCM
   - Command history and output streaming

## Data Model Extensions

### New PostgreSQL Tables

| Table | Purpose |
| :--- | :--- |
| `rootkit_configs` | Saved rootkit configuration templates |
| `rootkit_payloads` | Compiled payload binaries and metadata |
| `rootkit_instances` | Active rootkit instances per beacon |
| `rootkit_build_jobs` | Build server job tracking (F0207) |
| `rootkit_events` | Rootkit activity audit log |

### Beacon Table Extensions

```sql
ALTER TABLE beacons ADD COLUMN rootkit_instance_id UUID;
ALTER TABLE beacons ADD COLUMN rootkit_type VARCHAR(50);
ALTER TABLE beacons ADD COLUMN rootkit_status VARCHAR(50);
ALTER TABLE beacons ADD COLUMN stealth_mode_enabled BOOLEAN DEFAULT FALSE;
```

## Build Server Architecture (F0207)

The dynamic build server compiles rootkit payloads on-demand based on target specifications:

```text
+---------------+     +---------------+     +---------------+
|  Xero C2 API  |---->| Build Queue   |---->| Build Worker  |
|  (Trigger)    |     |  (Redis)      |     |  (Docker)     |
+---------------+     +---------------+     +-------+-------+
                                                    |
                                                    v
                                           +---------------+
                                           | Target Env    |
                                           | - Download    |
                                           |   kernel      |
                                           |   headers     |
                                           | - Compile     |
                                           |   rootkit     |
                                           | - Sign (opt)  |
                                           +-------+-------+
                                                   |
                                                   v
                                           +---------------+
                                           | Artifact      |
                                           | Storage       |
                                           | (F0015.01 S3) |
                                           +-------+-------+
                                                   |
                                                   v
                                           +---------------+
                                           | Xero C2 API   |
                                           | (Deliver to   |
                                           |  Beacon)      |
                                           +---------------+
```

## Test Plan

### Unit Tests
- [ ] Rootkit configuration schema validation
- [ ] Heartbeat interval calculation with jitter
- [ ] Encrypted shell protocol encode/decode
- [ ] Port knocker sequence detection
- [ ] Build job queue processing

### System / Integration Tests
- [ ] LKM rootkit hides process on Linux test VM
- [ ] eBPF rootkit hides file on Linux test VM
- [ ] Windows rootkit hides network connection
- [ ] Stealth mode stops heartbeat until wake
- [ ] Build server compiles kernel version-specific payload

### Playwright Tests
- [ ] Rootkit builder UI shows all configuration options
- [ ] Generate payload triggers build job and downloads artifact
- [ ] Rootkit management page shows active instances
- [ ] Encrypted shell session connects and executes commands

## Related Features

- **Core C2:** [F0015](0015-go-beacon-agent.md), [F0018](0018-interactive-shell-session.md)
- **Plugin System:** [F0041](0041-plugin-api.md)
- **Traffic Shaping:** [F0021](0021-traffic-shaping-profiles.md)
- **Post-Exploitation:** [F0101](0101-process-injection-token-impersonation.md), [F0108](0108-memory-only-beacon-execution.md)

## Security Considerations

- **Authorized Use:** Rootkit capabilities should only be deployed on authorized target systems with explicit written permission
- **Encryption:** All rootkit communications use AES-256-GCM with unique session keys
- **Audit Logging:** All rootkit actions logged to `rootkit_events` table
- **Operator Authorization:** Critical rootkit actions require operator confirmation
- **Payload Signing:** Optional kernel module signing for Linux distributions requiring signed modules

## Future Enhancements

- **macOS Rootkit:** Kernel extension and eBPF support for macOS
- **Container Rootkit:** Docker/Kubernetes namespace hiding
- **Cloud Rootkit:** AWS Nitro, Azure Fabric, GCP Visor integration
- **AI-Powered Evasion:** Machine learning-based behavior adaptation
