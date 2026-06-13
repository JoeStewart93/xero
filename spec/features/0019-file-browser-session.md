# F0019: File Browser Session

## Metadata
| Field | Value |
|---|---|
| ID | F0019 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 3 |
| Depends on | F0016, F0017 |

## Summary
Interactive file browser session allowing operators to list directories, navigate the remote filesystem, view file metadata, and preview text files on compromised hosts.

## Implementation Scope
- Read-only file browsing only: list, stat, and text preview.
- Upload, download, edit, delete, rename, search, and multi-select actions are out of scope for F0019.
- File browser launches from the Beacons host operations modal.
- File-browser operations use the existing `SESSION_DATA` frame with typed payload operations and request IDs.
- Default root is OS-aware on the beacon (`/` for Unix-like hosts, `C:\` for Windows when available).
- Paths after session open are relative to the session root.
- Directory listings are cached by the C2 session relay for 5 seconds; manual refresh bypasses cache.
- Text preview is UTF-8 only for F0019 and is limited to 1MB, with binary previews blocked.

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
- [x] Protocol messages for list_dir, stat, read_file
- [x] Error codes for access denied, not found, path invalid
- [x] Beacon implements file ops using OS-native APIs

### Stage 2: Backend session relay
**Goal:** Route file browser commands between UI and beacon.
**Acceptance Criteria:**
- [x] File browser session type registered in session manager
- [x] Request/response correlated by sequence ID
- [x] Directory listings cached for 5s to reduce beacon load

### Stage 3: File browser UI
**Goal:** Tree/table view with breadcrumb navigation.
**Acceptance Criteria:**
- [x] Directory listing renders files and folders with icons
- [x] Click folder navigates; breadcrumb allows jump to parent
- [x] Text file preview opens in side panel

## Feature Acceptance Criteria

- [x] Operator browses C:\ or /home directories on connected beacon
- [x] Access denied paths show clear error without session crash
- [x] File preview renders UTF-8 text files up to 1MB

## Test Plan

### Unit Tests
- [x] test_file_list_message_roundtrip
- [x] test_path_traversal_rejected
- [x] test_stat_returns_metadata_fields
- [x] test_read_file_truncates_at_limit
- [x] test_binary_file_preview_blocked

### System / Integration Tests
- [x] Open file browser; list root directory; entries match beacon FS
- [x] Navigate to subdirectory; listing updates correctly
- [x] Read text file; content matches on-disk file

### Playwright Tests
- [x] Open file browser from beacon actions menu
- [x] Navigate folders via breadcrumb and folder clicks
- [x] Preview text file shows content in side panel

## Implementation Notes

- Added a `file_browser` session type over the existing `SESSION_DATA` relay with `open`, `list_dir`, `stat`, `read_file`, `close`, and request IDs.
- Added C2 schemas, OpenAPI coverage, session relay validation, per-session directory-listing cache, and per-request file errors that do not fail the session.
- Added Go beacon read-only file operations with root scoping, traversal protection, metadata, UTF-8 preview, truncation, and binary preview blocking.
- Added Beacons host operation UI for opening file-browser sessions, navigating folders, using breadcrumbs, refreshing listings, and previewing text.

## Validation Evidence

- Backend unit and lint suites passed, including file-browser session, cache, traversal, and access-error coverage.
- Go beacon tests and build passed, including metadata, traversal, truncation, and binary preview blocking.
- Frontend lint, full Vitest suite, and production build passed.
- OpenAPI export and check passed.
- Rebuilt and restarted the C2 and BFF/frontend compose stacks.
- Connected the app to the live C2 service at `http://localhost:8001` and verified `artifact_store`, Postgres, and Redis readiness.
- Started a live Go beacon over websocket transport, opened the UI file browser, listed `/`, navigated `/workspace/platform`, and previewed `docker-compose.c2.yml`.
- Direct live websocket validation listed `/home` on the connected Linux beacon.

## Maintainability Review

- The feature reuses the existing session relay and websocket client instead of creating a parallel channel.
- File operations are isolated in `internal/filebrowser` on the beacon and file-browser-specific helpers in the C2 session module.
- The UI is contained to the Beacons operation modal with shared session client behavior; no broad refactor round is required after F0019.
