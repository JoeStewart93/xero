# F0019: File Browser Session

## Metadata
| Field | Value |
|---|---|
| ID | F0019 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0016, F0017 |

## Summary
Interactive file browser session allowing operators to list directories, navigate the remote filesystem, view file metadata, and preview text files on compromised hosts.

## Requirements
- Session type file_browser with directory listing and navigation
- List, stat, and read operations via session protocol messages
- Path traversal protection rejects .. beyond root scope
- File metadata: size, modified time, permissions, type
- Text preview limited to 1MB with binary detection

## Stages

### Stage 1: File ops protocol
**Goal:** Define SESSION_FILE_LIST, READ, STAT message types.
**Acceptance Criteria:**
- [ ] Protocol messages for list_dir, stat, read_file
- [ ] Error codes for access denied, not found, path invalid
- [ ] Beacon implements file ops using OS-native APIs

### Stage 2: Backend session relay
**Goal:** Route file browser commands between UI and beacon.
**Acceptance Criteria:**
- [ ] File browser session type registered in session manager
- [ ] Request/response correlated by sequence ID
- [ ] Directory listings cached for 5s to reduce beacon load

### Stage 3: File browser UI
**Goal:** Tree/table view with breadcrumb navigation.
**Acceptance Criteria:**
- [ ] Directory listing renders files and folders with icons
- [ ] Click folder navigates; breadcrumb allows jump to parent
- [ ] Text file preview opens in side panel

## Feature Acceptance Criteria

- [ ] Operator browses C:\ or /home directories on connected beacon
- [ ] Access denied paths show clear error without session crash
- [ ] File preview renders UTF-8 text files up to 1MB

## Test Plan

### Unit Tests
- [ ] test_file_list_message_roundtrip
- [ ] test_path_traversal_rejected
- [ ] test_stat_returns_metadata_fields
- [ ] test_read_file_truncates_at_limit
- [ ] test_binary_file_preview_blocked

### System / Integration Tests
- [ ] Open file browser; list root directory; entries match beacon FS
- [ ] Navigate to subdirectory; listing updates correctly
- [ ] Read text file; content matches on-disk file

### Playwright Tests
- [ ] Open file browser from beacon actions menu
- [ ] Navigate folders via breadcrumb and folder clicks
- [ ] Preview text file shows content in side panel
