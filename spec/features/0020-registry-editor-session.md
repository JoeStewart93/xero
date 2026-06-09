# F0020: Registry Editor Session

## Metadata
| Field | Value |
|---|---|
| ID | F0020 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0017 |

## Summary
Windows-only interactive registry editor session enabling operators to browse registry hives, read keys and values, and modify string and DWORD values with confirmation safeguards.

## Requirements
- Windows beacon only; session rejected on non-Windows targets
- Browse hives: HKLM, HKCU, HKU, HKCR, HKCC
- Read key values with type display (REG_SZ, REG_DWORD, etc.)
- Write string and DWORD values with operator confirmation
- Delete value requires explicit confirm dialog in UI

## Stages

### Stage 1: Registry protocol
**Goal:** Define SESSION_REG_LIST, READ, WRITE, DELETE messages.
**Acceptance Criteria:**
- [ ] Beacon uses Windows registry API via golang.org/x/sys/windows/registry
- [ ] List keys and values for given path
- [ ] Write validates value type matches requested type

### Stage 2: Safety guards
**Goal:** Prevent destructive operations without confirmation.
**Acceptance Criteria:**
- [ ] DELETE and WRITE require confirm_token from UI
- [ ] Hive root keys cannot be deleted
- [ ] Audit log records all registry modifications

### Stage 3: Registry UI
**Goal:** Tree view with value editor panel.
**Acceptance Criteria:**
- [ ] Hive tree expandable to keys and values
- [ ] Value editor supports string and DWORD input
- [ ] Confirm modal before write/delete operations

## Feature Acceptance Criteria

- [ ] Operator browses HKLM\Software and reads values
- [ ] Write DWORD value persists and readable on refresh
- [ ] Non-Windows beacon shows registry unavailable message

## Test Plan

### Unit Tests
- [ ] test_reg_list_keys_windows_mock
- [ ] test_reg_read_value_types
- [ ] test_reg_write_requires_confirm_token
- [ ] test_reg_delete_blocked_on_hive_root
- [ ] test_non_windows_session_rejected

### System / Integration Tests
- [ ] Open registry session on Windows beacon; list HKCU\Environment
- [ ] Write test REG_SZ value; read back confirms persistence
- [ ] Linux beacon registry session returns 400 unsupported

### Playwright Tests
- [ ] Registry editor available only for Windows beacons in UI
- [ ] Browse registry tree and view value details
- [ ] Write value shows confirmation dialog before applying
