# F0051: Nmap Wrapper with NSE Scripts

## Metadata
| Field | Value |
|---|---|
| ID | F0051 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0022, F0045, F0069 |

## Summary
Full-featured Nmap integration with script scanning capabilities. Provides OS detection, version detection, and NSE script execution with structured XML result parsing. Preset scan profiles for common use cases.

## Requirements
- Nmap binary execution from scanner service or C2 embedded scanner
- OS detection (-O) and version detection (-sV)
- NSE script categories: discovery, version, vuln, auth, default
- Preset scan profiles (quick, full, intensive, stealth)
- XML result parsing for structured data
- CVE extraction from script output
- Integration with asset inventory

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.100\", \"192.168.1.0/24\"],
    \"scan_type\": \"quick\",  # quick, full, intensive, stealth, custom
    \"script_categories\": [\"discovery\", \"version\"],  # vuln, auth, default, safe
    \"os_detection\": true,
    \"version_detection\": true,
    \"timing_template\": \"T4\",  # T0-T5 (paranoid to insane)
    \"output_format\": \"xml\",
    \"execution_target\": \"auto\",
    \"stream_results\": true
}
`

## Preset Scan Profiles

| Profile | Flags | Use Case | Duration |
| :--- | :--- | :--- | :--- |
| quick | -sV -T4 --top-ports 100 | Fast service detection | 30s |
| full | -sV -sC -O -T4 | Full scan with OS detection | 5min |
| intensive | -sV -sC -O -T3 --script vuln | Deep scan with vuln scripts | 15min |
| stealth | -sS -sV -T2 --scan-delay 1s | Low and slow | 10min |
| aggressive | -sS -sV -O -T4 --script=aggressive | Comprehensive | 20min |

## NSE Script Categories

| Category | Scripts | Purpose |
| :--- | :--- | :--- |
| discovery | roadcast-scan, dns-*, smb-* | Network/host discovery |
| version | http-enum, ssh2-enum-algos | Service version detection |
| vuln | http-vuln-*, smb-vuln-* | Vulnerability detection |
| auth | http-auth, ssh-auth-methods | Authentication testing |
| default |
map-se, http-title | Default scripts |
| safe | Non-intrusive scripts | Production-safe scanning |

## Result Schema

`json
{
    \"scan_id\": \"uuid\",
    \"status\": \"completed\",
    \"nmap_version\": \"7.94\",
    \"scan_args\": \"-sV -sC -O -T4\",
    \"hosts\": [
        {
            \"address\": \"192.168.1.100\",
            \"address_type\": \"ipv4\",
            \"status\": \"up\",
            \"os_detection\": {
                \"os_match\": {
                    \"name\": \"Linux 5.x\",
                    \"accuracy\": 95,
                    \"os_family\": \"Linux\",
                    \"os_gen\": \"Linux 5.4-5.14\"
                },
                \"os_cpe\": [\"cpe:/o:linux:linux_kernel:5.4\"]
            },
            \"ports\": [
                {
                    \"port\": 22,
                    \"protocol\": \"tcp\",
                    \"state\": \"open\",
                    \"reason\": \"syn-ack\",
                    \"service\": {
                        \"name\": \"ssh\",
                        \"product\": \"OpenSSH\",
                        \"version\": \"8.2p1\",
                        \"extrainfo\": \"Ubuntu Linux; protocol 2.0\",
                        \"cpe\": [\"cpe:/a:openssh:openssh:8.2p1\"]
                    },
                    \"scripts\": {
                        \"ssh-hostkey\": {
                            \"2048\": \"aa:bb:cc:dd... (RSA)\",
                            \"256\": \"11:22:33:44... (ECDSA)\"
                        },
                        \"ssh2-enum-algos\": {
                            \"kex_algos\": [\"curve25519-sha256\", ...],
                            \"server_host_key_algos\": [\"rsa-sha2-256\", ...],
                            \"encryption_algos\": [\"chacha20-poly1305@openssh.com\", ...]
                        }
                    }
                },
                {
                    \"port\": 443,
                    \"protocol\": \"tcp\",
                    \"state\": \"open\",
                    \"service\": {
                        \"name\": \"http\",
                        \"product\": \"nginx\",
                        \"version\": \"1.18.0\"
                    },
                    \"scripts\": {
                        \"http-title\": \"Welcome to nginx!\",
                        \"http-server-header\": \"nginx/1.18.0\",
                        \"ssl-cert\": {
                            \"subject\": {\"CN\": \"example.com\"},
                            \"issuer\": {\"CN\": \"Let's Encrypt\"},
                            \"valid_from\": \"2024-01-01\",
                            \"valid_to\": \"2024-04-01\"
                        }
                    }
                }
            ],
            \"vulnerabilities\": [
                {
                    \"cve\": \"CVE-2021-41617\",
                    \"severity\": \"medium\",
                    \"cvss\": 5.9,
                    \"service\": \"OpenSSH\",
                    \"version\": \"8.2p1\",
                    \"description\": \"OpenSSH < 8.5p1 NULL pointer dereference\",
                    \"script_id\": \"ssh-enum-versions\",
                    \"references\": [\"https://nvd.nist.gov/vuln/detail/CVE-2021-41617\"]
                }
            ]
        }
    ],
    \"summary\": {
        \"hosts_up\": 1,
        \"hosts_down\": 0,
        \"total_ports\": 2,
        \"open_ports\": 2,
        \"vulnerabilities_found\": 1,
        \"duration_seconds\": 45.2
    }
}
`

## Stages

### Stage 1: Nmap Module Backend
**Goal:** Register nmap in module registry with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.nmap
- [ ] Args validation for targets, scan_type, script_categories
- [ ] Scan profile flag expansion
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Nmap Execution
**Goal:** Execute nmap binary and parse XML results.
**Acceptance Criteria:**
- [ ] Nmap subprocess execution with XML output
- [ ] XML parsing for hosts, ports, services
- [ ] OS detection result parsing
- [ ] NSE script output extraction
- [ ] CVE extraction from vuln scripts

### Stage 3: Result Structuring
**Goal:** Normalize nmap output for UI display.
**Acceptance Criteria:**
- [ ] Host results structured with OS info
- [ ] Port results include service and script data
- [ ] Vulnerabilities extracted and categorized
- [ ] Summary statistics calculated

### Stage 4: Asset Integration
**Goal:** Link results to asset inventory.
**Acceptance Criteria:**
- [ ] Host assets created/updated
- [ ] Service assets linked to hosts
- [ ] Vulnerabilities linked to services
- [ ] OS detection enriches host metadata

## Feature Acceptance Criteria

- [ ] Nmap scan executes with selected profile
- [ ] XML output parsed correctly into structured JSON
- [ ] NSE script results extracted and formatted
- [ ] OS detection accuracy displayed
- [ ] CVEs extracted and linked to assets
- [ ] Scan can be cancelled mid-execution

## Test Plan

### Unit Tests
- [ ] test_nmap_args_validation
- [ ] test_scan_profile_flag_expansion
- [ ] test_nmap_command_construction
- [ ] test_xml_host_parsing
- [ ] test_xml_port_parsing
- [ ] test_nse_script_output_extraction
- [ ] test_cve_extraction_from_scripts

### System / Integration Tests
- [ ] Nmap quick scan completes against lab target
- [ ] OS detection returns accurate results
- [ ] Service version detection works
- [ ] NSE scripts execute and return output
- [ ] XML parsing handles edge cases
- [ ] Results create/update assets correctly

### Playwright Tests
- [ ] Nmap module visible in Recon module browser
- [ ] Scan profile dropdown shows options
- [ ] Script category checkboxes available
- [ ] Submit scan task with valid targets
- [ ] Results show OS detection with accuracy
- [ ] Port results show service versions and script output
- [ ] Vulnerabilities displayed with severity badges

## Nmap Command Construction

`python
def build_nmap_command(args: dict) -> list[str]:
    cmd = [\"nmap\"]

    # Scan type/profile
    if args[\"scan_type\"] == \"custom\":
        cmd.extend(args.get(\"custom_flags\", []))
    else:
        cmd.extend(get_scan_profile_flags(args[\"scan_type\"]))

    # OS and version detection
    if args.get(\"os_detection\"):
        cmd.append(\"-O\")
    if args.get(\"version_detection\"):
        cmd.append(\"-sV\")

    # Script categories
    scripts = get_script_categories(args.get(\"script_categories\", []))
    if scripts:
        cmd.append(f\"--script={scripts}\")

    # Timing
    cmd.append(f\"-T{args.get('timing_template', '4')}\")

    # Output format
    cmd.extend([\"-oX\", \"-\"])  # XML to stdout

    # Targets
    cmd.extend(args[\"targets\"])

    return cmd

def get_scan_profile_flags(profile: str) -> list[str]:
    profiles = {
        \"quick\": [\"-sV\", \"-T4\", \"--top-ports\", \"100\"],
        \"full\": [\"-sV\", \"-sC\", \"-O\", \"-T4\"],
        \"intensive\": [\"-sV\", \"-sC\", \"-O\", \"-T3\", \"--script\", \"vuln\"],
        \"stealth\": [\"-sS\", \"-sV\", \"-T2\", \"--scan-delay\", \"1s\"],
        \"aggressive\": [\"-sS\", \"-sV\", \"-O\", \"-T4\", \"--script\", \"aggressive\"],
    }
    return profiles.get(profile, [])

def get_script_categories(categories: list[str]) -> str:
    category_map = {
        \"discovery\": \"discovery\",
        \"version\": \"version\",
        \"vuln\": \"vuln\",
        \"auth\": \"auth\",
        \"default\": \"default\",
        \"safe\": \"safe\",
    }
    return \",\".join(category_map.get(c, c) for c in categories)
`

## Performance Considerations

- Large scans (>100 hosts) should stream progress
- Vuln scripts can be slow; consider timeout per script
- XML output can be large; parse incrementally if needed
- Consider --min-hostgroup and --max-hostgroup for parallelism

---

*End of Document*
