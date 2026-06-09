# F0035: SMB Enumeration

## Metadata
| Field | Value |
|---|---|
| ID | F0035 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016 |

## Summary
Built-in SMB enumeration module for discovering shares, sessions, users, and OS information on Windows networks within authorized lab scope. It uses the scanner execution model: embedded C2 scanner by default, external scanner selection when available, and later beacon pivot execution for internal vantage points.

## Requirements
- builtin.smbenum module with target, username, password, hash args
- Enumerate: shares, sessions, users, local groups, OS info
- Support null session and credential-based enumeration
- Results JSON structured per enumeration type
- Rate limited to 1 target per task for MVP
- Execution target defaults to embedded C2 scanner unless an external scanner or later pivot route is selected

## Stages

### Stage 1: SMB module schema
**Goal:** Register smbenum with auth and target args.
**Acceptance Criteria:**
- [ ] Args: target, auth_type (null/credential/ntlmhash), creds
- [ ] Enum types selectable: shares, users, sessions, os
- [ ] Results schema per enum type documented in module metadata

### Stage 2: Scanner SMB client
**Goal:** Scanner execution implements SMB negotiation and queries.
**Acceptance Criteria:**
- [ ] Null session share listing via SMB2
- [ ] User enumeration via SAMR or known techniques
- [ ] Auth failure returns structured error without hang

### Stage 3: Result display
**Goal:** UI renders SMB results in organized sections.
**Acceptance Criteria:**
- [ ] Shares table: name, type, permissions, comment
- [ ] Users list with rid and account flags
- [ ] OS info section shows version and domain

## Feature Acceptance Criteria

- [ ] Null session share listing works against lab Samba target
- [ ] Credential-based enumeration returns user list
- [ ] Auth failure reported clearly without scanner crash

## Test Plan

### Unit Tests
- [ ] test_smbenum_args_validation
- [ ] test_smb_share_list_parse_mock
- [ ] test_null_session_connection
- [ ] test_auth_failure_error_result
- [ ] test_result_schema_per_enum_type

### System / Integration Tests
- [ ] Run smbenum against lab Samba; shares match smbclient baseline
- [ ] Invalid credentials return auth error result
- [ ] SMB results ingested into asset inventory metadata

### Playwright Tests
- [ ] SMB enum module available in module browser
- [ ] Submit smbenum task; results show shares table
- [ ] Auth failure shows error message in result panel
