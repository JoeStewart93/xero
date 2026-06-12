# F0203: Windows Rootkit

## Metadata
| Field | Value |
|---|---|
| ID | F0203 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200 |

## Summary
Windows rootkit providing kernel-level and user-mode hiding and protection capabilities. Supports DKOM (Direct Kernel Object Manipulation), SSDT hooking, IDT hooking, and eBPF via BPF-for-Windows. Hides processes, files, network connections, and registry keys on Windows 10 and Windows 11.

## Requirements
- Windows 10 (1809+) and Windows 11 support
- x86_64 architecture
- Configurable hiding capabilities (process, file, network, registry)
- Configurable protection capabilities
- Driver signing support (Test Mode or EV Certificate)
- Compatibility with PatchGuard (Win10/11 64-bit)

## Rootkit Techniques

### DKOM (Direct Kernel Object Manipulation)
- Direct manipulation of EPROCESS structures
- Unlink process from active process list
- Hide threads from ETHREAD lists
- Bypass PatchGuard with careful memory management

### SSDT Hooking (System Service Descriptor Table)
- Hook syscall dispatch table
- Intercept NtQuerySystemInformation
- Filter process enumeration (SystemProcessInformation)
- PatchGuard aware on 64-bit

### IDT Hooking (Interrupt Descriptor Table)
- Hook interrupt handlers
- Less common on 64-bit Windows
- Used for legacy compatibility

### eBPF for Windows
- Via Microsoft eBPF for Windows
- Network filtering via XDP
- Requires eBPF runtime installation

### Callback Hooks
- PsSetCreateProcessNotifyRoutine
- CmRegisterCallbackEx for registry
- NdisRegisterProtocolChain for network

## Hiding Capabilities

### Process Hiding
**Techniques:**
- DKOM: Unlink from Prcb.ActiveProcess list
- SSDT: Hook NtQuerySystemInformation
- Callback: PsSetCreateProcessNotifyRoutine

**Hidden From:**
- Task Manager
- Process Explorer
- GetActiveProcessId()
- NtQuerySystemInformation()

### File Hiding
**Techniques:**
- Callback: CmRegisterCallbackEx
- Filter driver: Hide files in IRP_MN_QUERY_DIRECTORY
- MFT manipulation (advanced)

**Hidden From:**
- Windows Explorer
- dir command
- FindFirstFile/FindNextFile
- Registry file references

### Network Hiding
**Techniques:**
- TDIs (Transport Driver Interface) hooks
- Filter TCP/IP connection lists
- eBPF XDP for packet filtering

**Hidden From:**
- netstat
- Get-NetTCPConnection
- TCP connection tables

### Registry Hiding
**Techniques:**
- CmRegisterCallbackEx
- Hook CcpRetrieveCacheAttribute
- Hide keys/values on enumeration

**Hidden From:**
- reg query
- Registry Editor
- RegEnumKey/RegEnumValue

## Protection Capabilities

### File Locking
- Create named mutex per protected file
- Filter driver denies IRP_MJ_READ/WRITE
- ACL manipulation for access control

### Memory Locking
- VirtualLock() for user-mode
- PAGE_GUARD for exception on access
- Hide from CreateToolhelp32Snapshot

### Process Protection
- Job objects with limited inheritance
- Token manipulation for privilege control
- Hook NtTerminateProcess

## Driver Structure

`
platform/rootkits/windows/
+-- driver/
¦   +-- rootkit.sys         # Main driver
¦   +-- rootkit.vcxproj
¦   +-- dkom.c              # DKOM operations
¦   +-- ssdt.c              # SSDT hooking
¦   +-- callbacks.c         # System callbacks
¦   +-- hide_process.c
¦   +-- hide_file.c
¦   +-- hide_network.c
¦   +-- hide_registry.c
¦   +-- protect.c
¦   +-- ioctl.c             # User-driver communication
¦   +-- driver.h
+-- user/
¦   +-- rootkitctl.exe      # Control utility
¦   +-- config.c
¦   +-- communication.c     # C2 communication
+-- include/
¦   +-- ntddk.h
+-- scripts/
¦   +-- sign-driver.ps1
¦   +-- install-driver.ps1
+-- README.md
`

## PatchGuard Considerations (64-bit Windows)

| Technique | PatchGuard Safe | Notes |
| :--- | :--- | :--- |
| DKOM | Partial | Avoid kernel struct modification |
| SSDT Hooking | No | Use callback hooks instead |
| IDT Hooking | No | Rarely used on 64-bit |
| Inline Hooks | No | Use trampoline carefully |
| Callbacks | Yes | Recommended approach |
| eBPF | Yes | Native support |

## Driver Signing

### Test Mode (Development)
`powershell
bcdedit /set testsigning on
`

### Production Signing
- EV Certificate required
- Azure attestation or traditional signing
- Store in Windows Trusted Publisher

## Runtime Configuration

Control utility accepts JSON config:
`json
{
  "hidden_pids": [1234, 5678],
  "hidden_files": ["C:\\Windows\\Temp\\malware.exe"],
  "hidden_ports": [4444, 8080],
  "hidden_registry": ["HKLM\\SOFTWARE\\HiddenKey"],
  "protected_pids": [9999],
  "technique": "callback"
}
`

## Stages

### Stage 1: Driver Framework
**Goal:** Implement signed kernel driver with IOCTL interface.
**Acceptance Criteria:**
- [ ] Driver builds and signs successfully
- [ ] Driver installs and starts on Windows 10/11
- [ ] IOCTL communication with user-mode utility
- [ ] Graceful driver unload

### Stage 2: Process Hiding
**Goal:** Hide processes using callbacks.
**Acceptance Criteria:**
- [ ] Process hidden from Task Manager
- [ ] Process hidden from Process Explorer
- [ ] PatchGuard stable on 64-bit

### Stage 3: File/Network/Registry Hiding
**Goal:** Implement comprehensive hiding.
**Acceptance Criteria:**
- [ ] Files hidden from Explorer and dir
- [ ] Network connections hidden from netstat
- [ ] Registry keys hidden from reg query

### Stage 4: Protection Features
**Goal:** Implement protection capabilities.
**Acceptance Criteria:**
- [ ] Files protected from access
- [ ] Processes protected from termination
- [ ] Memory protected from debugging

## Feature Acceptance Criteria

- [ ] Rootkit loads on Windows 10 21H2 and Windows 11 22H2
- [ ] All hiding capabilities verified with standard tools
- [ ] PatchGuard stable (no BSOD) on 64-bit
- [ ] Driver unloads cleanly

## Test Plan

### Unit Tests
- [ ] test_ioctl_communication
- [ ] test_pid_filter_logic
- [ ] test_callback_registration

### System / Integration Tests
- [ ] Install driver; verify process hidden
- [ ] Verify file hidden from Explorer
- [ ] Verify network connection hidden
- [ ] Unload driver; verify system stable
- [ ] Test on Windows 10 and 11

### Playwright Tests
- [ ] Rootkit builder shows Windows options
- [ ] Generate Windows rootkit payload
- [ ] Deploy to beacon; verify active

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Persistence:** [F0204](0204-rootkit-persistence.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
