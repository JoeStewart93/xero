# F0202: Linux eBPF Rootkit

## Metadata
| Field | Value |
|---|---|
| ID | F0202 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0207 |

## Summary
Linux eBPF-based rootkit providing kernel-level hiding and protection with safer alternative to LKM. Uses eBPF programs (kprobes, tracepoints, cgroup BPF) to intercept kernel events and hide processes, files, network connections, and memory. Requires kernel 5.x+ with eBPF support.

## Requirements
- Linux kernel 5.x or newer with eBPF support
- Support for x86_64 and aarch64 architectures
- Configurable hiding capabilities (process, file, network, memory)
- Configurable protection capabilities
- No kernel module signing required
- Safe unload without kernel impact

## eBPF Program Types

### Kprobes/Kretprobes
- Dynamic function entry/exit hooking
- Used for syscall interception
- Overhead: minimal with JIT compilation

### Tracepoints
- Static kernel instrumentation points
- Lower overhead than kprobes
- Limited to predefined locations

### cgroup BPF
- Attach programs to cgroups
- Network filtering (cgroup/skb)
- Socket operations (cgroup/skc_attach)

### LSM BPF (kernel 5.10+)
- Linux Security Module hooks
- File access, capability checks
- Process lifecycle events

## Hiding Capabilities

### Process Hiding
- kprobe on seq_show_pid to filter process output
- tracepoint on sched_process_exit for tracking
- Map-based PID filtering

### File Hiding
- kprobe on iterate_dir / readdir
- LSM hook on file_open (kernel 5.10+)
- Filter dentry names in BPF map

### Network Hiding
- kprobe on seq_show_sock for ss/netstat
- cgroup/skb for active packet filtering
- Tracepoint on tcp_v4_send_packet

### Memory Hiding
- kprobe on proc_maps_open
- Filter VMA entries based on PID

## Protection Capabilities

### File Locking
- LSM BPF hook on file_permission
- Deny read/write based on PID and path

### Memory Locking
- kprobe on ptrace_attach
- Block debugger attachment to protected PIDs

### Process Protection
- LSM BPF hook on task_prctl
- kprobe on do_send_sig_info

## Architecture

platform/rootkits/linux-ebpf/
  src/
    bpf/
      hide_process.bpf.c
      hide_file.bpf.c
      hide_network.bpf.c
      hide_memory.bpf.c
      protect_file.bpf.c
      protect_memory.bpf.c
      protect_process.bpf.c
    user/
      main.c - User-space manager
      loader.c - BPF program loader
      maps.c - BPF map management
      config.c - Configuration
      communication.c - C2 communication
  include/
    bpf/bpf_helpers.h
  Makefile
  bpf2go/ - bpf2go generated code
  README.md

## Runtime Configuration

User-space manager accepts configuration via config.json:
{
  "hidden_pids": [1234, 5678],
  "hidden_files": ["/etc/shadow", "/root/.ssh/*"],
  "hidden_ports": [443, 8080],
  "protected_pids": [9999],
  "verbose": false
}

## Kernel Requirements

| Feature | Minimum Kernel | Notes |
| :--- | :--- | :--- |
| Basic eBPF/kprobes | 4.1 | Core eBPF support |
| BPF maps (hash, lru) | 4.1 | Data storage |
| cgroup BPF | 4.9 | Network filtering |
| LSM BPF | 5.10 | File/process hooks |
| BPF CO-RE | 5.5 + libbpf 0.6 | Kernel portability |

## CO-RE for Portability

Use libbpf CO-RE (Compile Once - Run Everywhere) for kernel portability across different kernel versions.

## Stages

### Stage 1: eBPF Framework
**Goal:** Implement BPF program loading and management.
**Acceptance Criteria:**
- [ ] libbpf-based loader for BPF programs
- [ ] BPF map creation and management
- [ ] User-space config interface
- [ ] Graceful program detachment

### Stage 2: Hiding Programs
**Goal:** Implement eBPF programs for hiding.
**Acceptance Criteria:**
- [ ] Process hiding via kprobe/seq_show_pid
- [ ] File hiding via LSM or kprobe
- [ ] Network hiding via cgroup BPF
- [ ] Memory hiding via proc_maps kprobe

### Stage 3: Protection Programs
**Goal:** Implement protection capabilities.
**Acceptance Criteria:**
- [ ] File permission blocking via LSM BPF
- [ ] ptrace blocking via kprobe
- [ ] Signal filtering via LSM BPF

### Stage 4: CO-RE Portability
**Goal:** Ensure cross-kernel compatibility.
**Acceptance Criteria:**
- [ ] CO-RE skeleton generation
- [ ] Test on kernels 5.4, 5.10, 5.15, 6.x
- [ ] Fallback for missing features

## Feature Acceptance Criteria

- [ ] eBPF programs load on Ubuntu 20.04, 22.04, CentOS 8
- [ ] All hiding capabilities verified (ps, ls, ss)
- [ ] Programs unload without kernel impact
- [ ] CO-RE ensures cross-kernel compatibility

## Test Plan

### Unit Tests
- [ ] test_bpf_program_load
- [ ] test_bpf_map_operations
- [ ] test_pid_filter_logic
- [ ] test_config_parsing

### System / Integration Tests
- [ ] Load eBPF programs; verify process hidden
- [ ] Verify file hidden from directory listing
- [ ] Verify network connection hidden
- [ ] Unload programs; verify no kernel impact
- [ ] Test on multiple kernel versions

### Playwright Tests
- [ ] Rootkit builder shows eBPF options
- [ ] Generate eBPF payload
- [ ] Deploy to beacon; verify active

## Advantages Over LKM

| Aspect | LKM | eBPF |
| :--- | :--- | :--- |
| Kernel Panic Risk | Higher | Lower (verified) |
| Signing Required | Yes (Secure Boot) | No |
| Kernel Version | Any | 4.1+ (5.10+ ideal) |
| Portability | Poor (per-kernel) | Good (CO-RE) |
| Debugging | Difficult | bpftrace, bpftool |
| Performance | Excellent | Excellent (JIT) |

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **LKM Alternative:** [F0201](0201-linux-lkm-rootkit.md)
- **Build Server:** [F0207](0207-rootkit-build-server.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
