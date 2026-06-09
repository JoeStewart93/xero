# F0108: Memory Only Beacon Execution

## Metadata
| Field | Value |
|---|---|
| ID | F0108 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015 |

## Summary
v2 beacon execution mode that runs entirely in memory without writing persistent binaries to disk, using reflective loading and in-memory module execution techniques.

## Requirements
- Memory-only loader for beacon payload on Windows and Linux
- No disk write of beacon binary in memory-only mode
- Module execution in memory without dropping files to disk
- Operator selects memory-only mode in beacon generation
- Forensic verification: no beacon file on disk after execution

## Stages

### Stage 1: Reflective loader
**Goal:** In-memory PE/ELF loader for beacon payload.
**Acceptance Criteria:**
- [ ] Loader accepts shellcode or reflective DLL format
- [ ] Windows: reflective DLL injection into current process
- [ ] Linux: memfd_create + fexecve for anonymous executable

### Stage 2: Module execution
**Goal:** Run task modules without disk artifacts.
**Acceptance Criteria:**
- [ ] Shell commands via in-memory pipe without script files
- [ ] File transfer uses memory buffer without temp files
- [ ] Module plugins loaded into memory-only sandbox

### Stage 3: Generation UI
**Goal:** Memory-only toggle in beacon builder.
**Acceptance Criteria:**
- [ ] Beacon builder offers memory-only output format
- [ ] Output: shellcode blob or loader stub only
- [ ] Documentation warns of authorized lab use only

## Feature Acceptance Criteria

- [ ] Memory-only beacon runs and callbacks without disk artifact in lab forensics check
- [ ] Shell task executes without cmd.exe script file on disk
- [ ] Memory-only mode selectable in beacon generation UI

## Test Plan

### Unit Tests
- [ ] test_reflective_loader_windows_mock
- [ ] test_memfd_loader_linux_mock
- [ ] test_shell_no_disk_artifact
- [ ] test_memory_module_load

### System / Integration Tests
- [ ] Deploy memory-only beacon; register; complete echo task
- [ ] Filesystem audit shows no beacon binary written
- [ ] Shell session produces no script temp files

### Playwright Tests
- [ ] Beacon builder shows memory-only toggle
- [ ] Generate memory-only payload; download shellcode blob
- [ ] Memory-only beacon registers and appears in beacon list
