# F0020: Registry Editor Session

## Metadata
| Field | Value |
|---|---|
| ID | F0020 |
| Priority | P0 |
| Status | Complete |
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

## Approved Implementation Scope
- Reuse the existing session data channel with registry-specific JSON operations rather than adding new binary message types.
- Support browsing keys, reading values, writing REG_SZ and REG_DWORD values, and deleting values only. Registry key deletion is out of scope.
- Treat unsupported registry value types as read-only in the UI.
- Require a server-minted, single-use confirm_token for every write or delete request.
- Record registry modification audit metadata without storing raw registry value contents.
- Allow write and delete value requests across supported hives when the beacon process has operating-system permission; validation and live tests use disposable HKCU paths.

## Stages

### Stage 1: Registry protocol
**Goal:** Define SESSION_REG_LIST, READ, WRITE, DELETE messages.
**Acceptance Criteria:**
- [x] Beacon uses Windows registry API via golang.org/x/sys/windows/registry
- [x] List keys and values for given path
- [x] Write validates value type matches requested type

### Stage 2: Safety guards
**Goal:** Prevent destructive operations without confirmation.
**Acceptance Criteria:**
- [x] DELETE and WRITE require confirm_token from UI
- [x] Hive root keys cannot be deleted
- [x] Audit log records all registry modifications

### Stage 3: Registry UI
**Goal:** Tree view with value editor panel.
**Acceptance Criteria:**
- [x] Hive tree expandable to keys and values
- [x] Value editor supports string and DWORD input
- [x] Confirm modal before write/delete operations

## Feature Acceptance Criteria

- [x] Operator browses HKLM\Software and reads values
- [x] Write DWORD value persists and readable on refresh
- [x] Non-Windows beacon shows registry unavailable message

## Test Plan

### Unit Tests
- [x] `platform/tests/unit/test_c2_api.py::test_registry_session_open_sends_session_data_to_connected_windows_beacon`
- [x] `platform/tests/unit/test_c2_api.py::test_registry_session_rejects_non_windows_beacon`
- [x] `platform/tests/unit/test_c2_api.py::test_registry_request_rejects_key_delete_operations`
- [x] `platform/tests/unit/test_c2_api.py::test_registry_confirmation_token_is_single_use_and_bound_to_value`
- [x] `platform/tests/unit/test_c2_api.py::test_registry_session_data_records_redacted_modification_audit`
- [x] `platform/beacons/go/internal/registryeditor` manager normalization and non-Windows tests

### System / Integration Tests
- [x] Rebuilt and restarted C2 and BFF stacks with Docker Compose
- [x] Connected a live Windows beacon to C2 over WebSocket transport
- [x] Opened registry session on live Windows beacon; listed HKLM\Software and read HKLM\Software\Microsoft\Windows NT\CurrentVersion ProductName
- [x] Wrote disposable HKCU REG_DWORD value, read it back through the registry session, deleted it, and confirmed read-after-delete returns not_found
- [x] Non-Windows registry session returns 400 unsupported
- [x] Live audit rows contain operation metadata, value length, and digest without raw registry value contents
- [x] Removed live validation beacons, registry key, and temporary beacon artifacts after validation

### Frontend / Browser Tests
- [x] Registry editor available only for Windows beacons in UI
- [x] Browse registry tree and view value details
- [x] Write and delete values show confirmation dialog before applying
- [x] Live browser smoke verified C2 connection, Windows registry panel, and non-Windows unavailable state

## Validation
- [x] `python platform\scripts\ci.py backend-unit`
- [x] `python platform\scripts\ci.py backend-lint`
- [x] `python platform\scripts\ci.py openapi-export`
- [x] `python platform\scripts\ci.py openapi-check`
- [x] `python platform\scripts\ci.py go-beacon-test`
- [x] `python platform\scripts\ci.py go-beacon-build`
- [x] `npm --prefix platform\frontend test -- --run`
- [x] `npm --prefix platform\frontend run lint`
- [x] `npm --prefix platform\frontend run build`
- [x] `docker compose -f platform\docker-compose.c2.yml up -d --build`
- [x] `docker compose -f platform\docker-compose.bff.yml up -d --build`
- [x] `curl.exe -s http://localhost:8001/ready`
- [x] `curl.exe -s http://localhost:8000/ready`

## Maintainability Review
- Registry protocol validation, confirmation-token enforcement, and redacted audit handling are isolated in `xero_c2.registry_sessions`.
- Beacon registry operations are isolated behind the `registryeditor.Manager` package with Windows and non-Windows implementations split by build tags.
- Frontend registry behavior is isolated in `RegistrySessionPanel`, with the Beacons page only selecting the operation view.
- No follow-up refactor round required before merge.
