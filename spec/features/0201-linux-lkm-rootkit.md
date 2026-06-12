# F0201: Linux LKM Rootkit

## Metadata
| Field | Value |
|---|---|
| ID | F0201 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0207 |

## Summary
Linux Loadable Kernel Module (LKM) rootkit providing kernel-level hiding and protection capabilities. Hooks kernel system calls and data structures to hide processes, files, network connections, and memory. Supports dynamic compilation for target kernel versions via F0207 build server.

## Requirements
- Kernel module compatible with Linux kernels 4.x through 6.x
- Support for x86_64 and aarch64 architectures
- Configurable hiding capabilities (process, file, network, memory)
- Configurable protection capabilities (file lock, memory lock, process protect)
- Module signing support for Secure Boot environments
- Graceful unload without kernel panic

## Hiding Capabilities

### Process Hiding
**Hooked Functions:**
- get_pid_task() - Hide from /proc
- proc_fill_cache() - Hide from procfs
- __d_lookup() - Directory lookups
- seq_show_pid() - Hide from ps/top/htop

**Technique:** Unlink process from kernel task_struct lists and filter procfs output

### File Hiding
**Hooked Functions:**
- iterate_dir() - Hide from readdir
- d_rehash() - Hide from dentry cache
- lookup_one_len() - Hide from path resolution

**Technique:** Filter dentry names matching hidden file patterns

### Network Hiding
**Hooked Functions:**
- 	cp_v4_get_port() / 	cp_v6_get_port() - Port allocation
- inet_csk_get_port() - Connection tracking
- seq_show_sock() - Hide from ss/netstat
- /proc/net/tcp* - Procfs filtering

**Technique:** Filter socket structures from network listings

### Memory Hiding
**Hooked Functions:**
- get_mm_exe_file() - Hide executable path
- proc_maps_open() - Hide from /proc/[pid]/maps
- kallsyms_lookup_name() - Hide kernel symbols

## Protection Capabilities

### File Locking
- Intercept fs_read(), fs_write(), fs_unlink()
- Block access based on PID whitelist/blacklist
- Optional: Encrypt file content on-disk

### Memory Locking
- Use mprotect() to set pages as private
- Intercept ptrace() calls from debuggers
- Hide memory regions from /proc/[pid]/mem

### Process Protection
- Hook do_send_sig_info() to filter kill signals
- Hook do_exit() to prevent process termination
- Whitelist PIDs that can send signals

## Kernel Version Compatibility

| Kernel Version | Hooks Required | Special Considerations |
| :--- | :--- | :--- |
| 4.x | Classic syscall hooks | Kallsyms exposed |
| 5.x | Kprobes recommended | LOCKDEP warnings |
| 6.x | eBPF fallback option | CONFIG_DEBUG_KERNEL impacts |

## Module Structure

`
platform/rootkits/linux-lkm/
+-- src/
¦   +-- main.c              # Module init/exit
¦   +-- hook.c              # Function hooking (Kprobes/LKM)
¦   +-- hook.h
¦   +-- hide_process.c      # Process hiding
¦   +-- hide_file.c         # File hiding
¦   +-- hide_network.c      # Network hiding
¦   +-- hide_memory.c       # Memory hiding
¦   +-- protect_file.c      # File protection
¦   +-- protect_memory.c    # Memory protection
¦   +-- protect_process.c   # Process protection
¦   +-- config.c            # Runtime configuration
¦   +-- communication.c     # C2 communication (user space)
+-- include/
¦   +-- rootkit.h           # Public headers
+-- Makefile                # Kernel module build
+-- Kconfig                 # Kernel config options
+-- README.md
`

## Runtime Configuration

Module parameters (set at insmod or via /sys/module):

`
hidden_pids=1234,5678       # PIDs to hide
hidden_files=/etc/shadow    # Files to hide (glob patterns)
hidden_ports=443,8080       # Ports to hide
protected_pids=9999         # PIDs protected from kill
protected_files=/root/.ssh  # Files protected from access
memory_protect=1            # Enable memory hiding
verbose=0                   # Debug logging
`

## Build Process (F0207 Integration)

The build server compiles the LKM for target kernel:

1. Download kernel headers matching target uname -r
2. Configure for target architecture
3. Compile module with appropriate flags
4. Optionally sign with provided key
5. Upload artifact to Xero C2 for beacon delivery

## Stages

### Stage 1: Core Hooking Framework
**Goal:** Implement reliable kernel function hooking.
**Acceptance Criteria:**
- [ ] Kprobes-based hooking for modern kernels
- [ ] Classic inline hooking fallback for older kernels
- [ ] Hook installation/removal without kernel panic
- [ ] Support for x86_64 and aarch64

### Stage 2: Hiding Implementation
**Goal:** Implement all hiding capabilities.
**Acceptance Criteria:**
- [ ] Process hidden from ps, top, /proc
- [ ] Files hidden from ls, find, /proc
- [ ] Network connections hidden from ss, netstat
- [ ] Memory regions hidden from debuggers

### Stage 3: Protection Implementation
**Goal:** Implement protection capabilities.
**Acceptance Criteria:**
- [ ] Files protected from read/write/delete
- [ ] Memory protected from ptrace
- [ ] Processes protected from kill signals

### Stage 4: Build Server Integration
**Goal:** Dynamic compilation for target kernels.
**Acceptance Criteria:**
- [ ] Build server downloads correct kernel headers
- [ ] Module compiles for target kernel version
- [ ] Signed module option for Secure Boot

## Feature Acceptance Criteria

- [ ] LKM loads successfully on test VMs (Ubuntu 20.04, 22.04, CentOS 7, 8)
- [ ] All hiding capabilities verified with standard tools (ps, ls, ss)
- [ ] Module unloads cleanly without kernel panic
- [ ] Build server produces working module for target kernel

## Test Plan

### Unit Tests
- [ ] test_hook_install_remove
- [ ] test_pid_filter_function
- [ ] test_filename_match_pattern
- [ ] test_port_filter_function

### System / Integration Tests
- [ ] Load module; verify process hidden from ps/top
- [ ] Load module; verify file hidden from ls/find
- [ ] Load module; verify connection hidden from ss/netstat
- [ ] Send kill signal to protected process; verify blocked
- [ ] Unload module; verify kernel stable

### Playwright Tests
- [ ] Rootkit builder shows LKM options
- [ ] Generate LKM payload for target kernel
- [ ] Deploy to beacon; verify rootkit active

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **eBPF Alternative:** [F0202](0202-linux-ebpf-rootkit.md)
- **Build Server:** [F0207](0207-rootkit-build-server.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
