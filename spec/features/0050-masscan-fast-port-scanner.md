# F0050: Masscan Fast Port Scanner

## Metadata
| Field | Value |
|---|---|
| ID | F0050 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0022, F0045, F0069 |

## Summary
Ultra-fast port scanning module using masscan for large IP range discovery. Capable of scanning entire internet in under 6 minutes with appropriate rate limiting. Results streamed in real-time via WebSocket to UI. Auto-triggers service enumeration on discovered open ports.

## Requirements
- masscan binary execution from scanner service or C2 embedded scanner
- CIDR and IP list target support
- Configurable port ranges (presets and custom)
- Rate limiting to prevent network flooding
- Real-time result streaming via WebSocket
- Auto-creation of host assets for discovered hosts
- Integration with F0023 service enumeration

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.0/24\", \"10.0.0.0/8\", \"8.8.8.8\"],  # CIDR or IPs
    \"ports\": \"top-1000\",  # top-100, top-1000, top-10000, 1-65535, or custom
    \"rate\": 10000,  # packets/second (default 10000)
    \"timeout_ms\": 30000,  # scan timeout
    \"exclude\": [\"192.168.1.1\"],  # IPs to exclude
    \"execution_target\": \"auto\",  # embedded, scanner_worker, beacon
    \"auto_service_enum\": true,  # Trigger F0023 on open ports
    \"stream_results\": true  # Stream via WebSocket
}
`

## Port Presets

| Preset | Ports | Use Case |
| :--- | :--- | :--- |
| top-100 | Most common 100 ports | Quick scan |
| top-1000 | Most common 1000 ports | Standard scan |
| top-10000 | Most common 10000 ports | Comprehensive |
| all | 1-65535 | Full scan |
| web | 80,443,8080,8443,8000-8010 | Web services |
| database | 3306,5432,27017,6379,1433 | Database services |

## Result Schema

`json
{
    \"scan_id\": \"uuid\",
    \"status\": \"running\",  // running, completed, failed
    \"progress\": {
        \"targets_total\": 65536,
        \"targets_scanned\": 32768,
        \"percent_complete\": 50.0,
        \"ports_discovered\": 127,
        \"duration_seconds\": 45.2
    },
    \"results\": [
        {
            \"host\": \"192.168.1.100\",
            \"port\": 443,
            \"protocol\": \"tcp\",
            \"state\": \"open\",
            \"latency_ms\": 2.3,
            \"discovered_at\": \"2024-01-15T10:30:00Z\"
        },
        {
            \"host\": \"192.168.1.100\",
            \"port\": 80,
            \"protocol\": \"tcp\",
            \"state\": \"open\",
            \"latency_ms\": 1.8,
            \"discovered_at\": \"2024-01-15T10:30:01Z\"
        }
    ],
    \"summary\": {
        \"total_hosts\": 15,
        \"total_open_ports\": 42,
        \"most_common_ports\": [443, 80, 22]
    },
    \"assets_created\": [\"asset_id_1\", \"asset_id_2\"],  // F0071 integration
    \"service_enum_triggered\": true,  // F0023 auto-trigger
    \"service_enum_task_id\": \"task_uuid\"
}
`

## WebSocket Events

### Scan Progress Update
`json
{
    \"event\": \"scan_progress\",
    \"scan_id\": \"uuid\",
    \"data\": {
        \"targets_scanned\": 32768,
        \"targets_total\": 65536,
        \"percent_complete\": 50.0,
        \"ports_discovered\": 127,
        \"duration_seconds\": 45.2
    }
}
`

### New Port Discovered
`json
{
    \"event\": \"port_discovered\",
    \"scan_id\": \"uuid\",
    \"data\": {
        \"host\": \"192.168.1.100\",
        \"port\": 443,
        \"protocol\": \"tcp\",
        \"state\": \"open\"
    }
}
`

### Scan Complete
`json
{
    \"event\": \"scan_complete\",
    \"scan_id\": \"uuid\",
    \"data\": {
        \"total_hosts\": 15,
        \"total_open_ports\": 42,
        \"duration_seconds\": 120.5
    }
}
`

## Stages

### Stage 1: Masscan Module Backend
**Goal:** Register masscan in module registry with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.masscan
- [ ] Args validation for targets, ports, rate
- [ ] Port preset expansion (top-1000 ? actual ports)
- [ ] Target CIDR expansion
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Masscan Execution
**Goal:** Execute masscan binary and parse results.
**Acceptance Criteria:**
- [ ] masscan subprocess execution
- [ ] XML output parsing for structured results
- [ ] Rate limiting via --rate flag
- [ ] Timeout handling
- [ ] Error handling for unreachable targets

### Stage 3: Real-time Streaming
**Goal:** Stream results via WebSocket.
**Acceptance Criteria:**
- [ ] Progress updates every 1000 hosts scanned
- [ ] Individual port discovery events
- [ ] Scan complete event with summary
- [ ] Redis pub/sub for WebSocket delivery

### Stage 4: Asset Integration
**Goal:** Auto-create assets and trigger service enum.
**Acceptance Criteria:**
- [ ] Host assets created for discovered hosts (F0071)
- [ ] Service enum auto-triggered on open ports (F0023)
- [ ] Results linked to assets
- [ ] Deduplication for existing assets

## Feature Acceptance Criteria

- [ ] /16 network scans complete in < 60 seconds at rate 10000
- [ ] Results streamed in real-time to UI via WebSocket
- [ ] Open ports trigger automatic asset creation
- [ ] Service enumeration auto-triggered for open ports
- [ ] Rate limiting prevents network flooding
- [ ] Scan can be cancelled mid-execution

## Test Plan

### Unit Tests
- [ ] test_masscan_args_validation
- [ ] test_port_preset_expansion
- [ ] test_cidr_target_expansion
- [ ] test_masscan_command_construction
- [ ] test_xml_result_parsing
- [ ] test_rate_limiting_calculation

### System / Integration Tests
- [ ] Masscan scan executes against lab target
- [ ] Results match nmap baseline for open ports
- [ ] WebSocket events received in real-time
- [ ] Host assets created for discovered hosts
- [ ] Service enum task triggered automatically
- [ ] Cancel scan mid-execution works

### Playwright Tests
- [ ] Masscan module visible in Recon module browser
- [ ] Port preset dropdown shows options
- [ ] Submit scan task with valid targets
- [ ] Progress bar updates during scan
- [ ] Results table shows discovered ports
- [ ] Click port triggers service enum context menu

## Masscan Command Construction

`python
def build_masscan_command(args: dict) -> list[str]:
    ports = expand_port_preset(args[\"ports\"])
    targets = expand_targets(args[\"targets\"])
    exclude = args.get(\"exclude\", [])

    cmd = [
        \"masscan\",
        *targets,
        \"-p\", \",\".join(map(str, ports)),
        \"--rate\", str(args[\"rate\"]),
        \"--timeout\", str(args[\"timeout_ms\"]),
        \"-oX\", \"-\",  # XML to stdout
    ]

    if exclude:
        cmd.extend([\"--exclude\", \",\".join(exclude)])

    return cmd

def expand_port_preset(preset: str) -> list[int]:
    presets = {
        \"top-100\": [22, 80, 443, ...],  # Most common 100
        \"top-1000\": [...],  # Most common 1000
        \"top-10000\": [...],  # Most common 10000
        \"all\": list(range(1, 65536)),
        \"web\": [80, 443, 8080, 8443] + list(range(8000, 8011)),
        \"database\": [3306, 5432, 27017, 6379, 1433, 5984, 9200],
    }

    if preset in presets:
        return presets[preset]

    # Parse custom range like \"1-1024,3306,8080\"
    return parse_port_range(preset)
`

## Performance Targets

| Target Size | Rate | Expected Duration |
| :--- | :--- | :--- |
| /24 (256 hosts) | 10000 | < 5 seconds |
| /16 (65536 hosts) | 10000 | < 60 seconds |
| /8 (16M hosts) | 10000 | ~27 minutes |
| Entire internet | 100000 | ~6 minutes |

---

*End of Document*
