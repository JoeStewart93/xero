# F0103: Lateral Movement Modules

## Metadata
| Field | Value |
|---|---|
| ID | F0103 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0016, F0102 |

## Summary
v2 lateral movement modules supporting WMI, WinRM, SSH, and PsExec techniques for pivoting through authorized lab networks using harvested credentials.

## Requirements
- Modules: wmi_exec, winrm_exec, ssh_exec, psexec
- Credential input from F0102 results or manual operator entry
- Movement result creates new beacon registration on target if successful
- Technique selection based on target OS and available services
- Full audit trail of lateral movement attempts

## Stages

### Stage 1: Movement module suite
**Goal:** Implement four lateral movement techniques.
**Acceptance Criteria:**
- [ ] wmi_exec executes command via WMI on Windows targets
- [ ] winrm_exec uses WinRM for remote PowerShell execution
- [ ] ssh_exec connects via SSH with key or password auth
- [ ] psexec deploys service binary for remote execution

### Stage 2: Pivot integration
**Goal:** Successful movement spawns new beacon on target.
**Acceptance Criteria:**
- [ ] Movement task includes payload beacon binary option
- [ ] Success result includes new_beacon_id if callback received
- [ ] Failed movement returns error with technique-specific code

### Stage 3: Credential chaining
**Goal:** Use harvested creds from F0102 as movement input.
**Acceptance Criteria:**
- [ ] Task form offers credential picker from prior harvest results
- [ ] Credential used in memory only; not stored in task args plaintext
- [ ] Movement audit log links to credential source task ID

## Feature Acceptance Criteria

- [ ] WMI exec runs command on lab Windows target from beacon
- [ ] Successful pivot registers new beacon visible in UI
- [ ] Failed movement shows technique-specific error in result

## Test Plan

### Unit Tests
- [ ] test_wmi_exec_args_validation
- [ ] test_winrm_auth_methods
- [ ] test_ssh_key_and_password_auth
- [ ] test_psexec_service_lifecycle
- [ ] test_pivot_beacon_registration

### System / Integration Tests
- [ ] WMI exec against lab host; command output returned
- [ ] Pivot with payload; new beacon appears in list within 60s
- [ ] Use harvested credential; movement succeeds without manual entry

### Playwright Tests
- [ ] Lateral movement modules visible in v2 module browser
- [ ] Credential picker populated from prior harvest tasks
- [ ] New beacon from pivot appears in beacon list with pivot badge
