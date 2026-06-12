# F0229: Rootkit Evasion Testing

## Metadata
| Field | Value |
|---|---|
| ID | F0229 |
| Priority | High |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0220, F0206 |

## Summary
Comprehensive testing framework for verifying rootkit evasion against detection tools including rkhunter, chkrootkit, AIDE, Tripwire, and EDR products.

## Detection Tool Test Matrix

### rkhunter Tests

| Test | Command | Expected Result |
|---|---|---|
| File Properties | rkhunter --check properties | PASS |
| Known Rootkits | rkhunter --check known_rkts | PASS |
| Hidden Processes | rkhunter --check hidden_procs | PASS |
| Hidden Ports | rkhunter --check hidden_ports | PASS |
| Loaded Modules | rkhunter --check loaded_modules | PASS |
| Startup Files | rkhunter --check startup_files | PASS |

### chkrootkit Tests

| Test | Command | Expected Result |
|---|---|---|
| Binary Scanning | chkrootkit | PASS |
| LKM Detection | chkrootkit -v chkproc | PASS |
| Directory Check | chkrootkit -v chkdirs | PASS |
| Promisc Mode | chkrootkit -v ifpromisc | PASS |

### AIDE Tests

| Test | Command | Expected Result |
|---|---|---|
| File Integrity | aide --check | No changes |
| Attribute Check | aide --check | No attribute changes |

### Tripwire Tests

| Test | Command | Expected Result |
|---|---|---|
| Policy Check | tripwire --check | No violations |

## EDR Product Testing

### Commercial EDR
- [ ] CrowdStrike Falcon
- [ ] Carbon Black
- [ ] SentinelOne
- [ ] Windows Defender ATP
- [ ] Symantec Endpoint Protection

### Open Source EDR
- [ ] Osquery
- [ ] Wazuh
- [ ] OSSEC

## Test Scripts

### rkhunter Test Script
```bash
#!/bin/bash
# test_rkhunter_evasion.sh

echo "=== RKHunter Evasion Test ==="

# Update database
rkhunter --update

# Run full check
rkhunter --check --sk --rwo

# Check specific tests
rkhunter --enable properties --check
rkhunter --enable hidden_procs --check
rkhunter --enable hidden_ports --check
rkhunter --enable loaded_modules --check

# Parse results
if grep -q "WARNING" /var/log/rkhunter.log; then
    echo "FAILED: Warnings detected"
    exit 1
else
    echo "PASSED: No warnings"
    exit 0
fi
```

### chkrootkit Test Script
```bash
#!/bin/bash
# test_chkrootkit_evasion.sh

echo "=== Chkrootkit Evasion Test ==="

# Run full check
./chkrootkit

# Check specific tests
./chkrootkit -v chkproc
./chkrootkit -v chkdirs
./chkrootkit -v ifpromisc

# Parse results
if grep -q "INFECTED" /tmp/chkrootkit.log; then
    echo "FAILED: Infections detected"
    exit 1
else
    echo "PASSED: No infections"
    exit 0
fi
```

## Test Environments

### Linux VMs
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS
- CentOS 7
- CentOS Stream 9
- Debian 11

### Windows VMs
- Windows 10 21H2
- Windows 10 22H2
- Windows 11 22H2

## Test Report Format

```json
{
  "test_id": "rkhunter_ubuntu_2204",
  "tool": "rkhunter",
  "version": "1.8.3",
  "platform": "Ubuntu 22.04",
  "kernel": "5.15.0-91-generic",
  "timestamp": "2024-01-01T00:00:00Z",
  "results": {
    "properties": "PASS",
    "known_rkts": "PASS",
    "hidden_procs": "PASS",
    "hidden_ports": "PASS",
    "loaded_modules": "PASS"
  },
  "overall": "PASS",
  "warnings": [],
  "notes": "All evasion techniques working"
}
```

## Stages

### Stage 1: Test Framework
- [ ] Automated test scripts
- [ ] Result parsing
- [ ] Report generation

### Stage 2: Detection Tool Tests
- [ ] rkhunter full test suite
- [ ] chkrootkit full test suite
- [ ] AIDE/Tripwire tests

### Stage 3: EDR Tests
- [ ] Windows Defender tests
- [ ] Osquery tests
- [ ] Commercial EDR tests

### Stage 4: CI Integration
- [ ] Automated test runs
- [ ] Test reporting dashboard
- [ ] Regression testing

## Feature Acceptance Criteria
- [ ] Pass rkhunter --check on all Linux test VMs
- [ ] Pass chkrootkit on all Linux test VMs
- [ ] Pass Windows Defender scan on Windows VMs
- [ ] Test automation integrated in CI
- [ ] Test reports generated automatically

## Test Plan

### Unit Tests
- [ ] test_rkhunter_parser
- [ ] test_chkrootkit_parser
- [ ] test_report_generation

### System Tests
- [ ] Run full rkhunter test suite
- [ ] Run full chkrootkit test suite
- [ ] Run EDR product scans

### Playwright Tests
- [ ] View test results in UI
- [ ] Generate test reports
- [ ] Compare test results across versions
