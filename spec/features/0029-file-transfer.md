# F0029: File Transfer

## Metadata
| Field | Value |
|---|---|
| ID | F0029 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 4 |
| Depends on | F0016, F0015, F0015.01-AMD |

## Summary
Upload and download files between operator workstation and beacon filesystem via chunked transfer protocol with integrity verification and progress tracking.

## Implementation Decisions
- UI planning started with Stitch project `projects/15583606350207588045`.
- Context7 lookup was attempted for React file-input handling, but the connector returned an expired OAuth token; implementation follows existing repo React, Playwright, and C2 patterns.
- MVP file-transfer operations are carried over existing encrypted `SESSION_DATA` frames as explicit transfer ops rather than new top-level protocol message types.
- Default transfer chunk size is 512 KiB to stay below the current 1 MiB encrypted frame cap after JSON/base64/framing overhead.
- File-browser UI provides the operator context, but transfer state, progress, chunk acknowledgement, and artifact linkage live in a dedicated file-transfer boundary.
- Upload overwrite requires explicit operator confirmation.
- Resume scope covers operator/browser retry and beacon reconnect using last acknowledged chunks; full process-restart resume is limited to persisted transfer/artifact metadata.

## Requirements
- Upload file from operator to beacon path via task module
- Download file from beacon to operator via task module
- Chunked transfer with SHA-256 per-chunk and whole-file hash
- Resume interrupted upload from last acknowledged chunk
- Max file size configurable; default 100MB for MVP
- Operator uploads and beacon downloads use the F0015.01-AMD artifact store for durable transfer staging and retrieval.

## Stages

### Stage 1: Transfer protocol
**Goal:** Define FILE_UPLOAD and FILE_DOWNLOAD message sequences.
**Acceptance Criteria:**
- [x] Transfer init frame includes filename, size, sha256, direction
- [x] Chunks numbered with 512 KiB default chunk size
- [x] ACK per chunk; NACK triggers retransmit
- [x] Transfer ops are validated as file-browser `SESSION_DATA` payloads without changing protocol version

### Stage 2: Backend orchestration
**Goal:** Task modules builtin.upload and builtin.download.
**Acceptance Criteria:**
- [x] Upload task stores operator file in temp storage then streams to beacon
- [x] Download task reassembles beacon chunks into downloadable artifact
- [x] Transfer progress published via WebSocket events

### Stage 3: Transfer UI
**Goal:** File picker upload and download buttons in file browser.
**Acceptance Criteria:**
- [x] Upload button in file browser uploads to current directory
- [x] Download button on file row saves to operator machine
- [x] Progress bar shows chunk percentage during transfer

## Feature Acceptance Criteria

- [x] 100MB file upload completes with matching SHA-256 on beacon disk
- [x] Interrupted upload resumes from last ACK without re-uploading prior chunks
- [x] Downloaded file matches on-beacon source file hash

## Test Plan

### Unit Tests
- [x] test_chunk_hash_verification
- [x] test_upload_resume_from_chunk_n
- [x] test_download_reassembly
- [x] test_max_file_size_rejected
- [x] test_nack_retransmit

### System / Integration Tests
- [x] Upload test file; verify on beacon filesystem via file browser
- [x] Download file from beacon; hash matches source
- [x] Simulate network drop mid-upload; resume completes successfully

### Playwright Tests
- [x] Upload file via file browser; progress bar reaches 100%
- [x] Download file from beacon row; browser saves file
- [x] Transfer failure shows retry option with resume

## Validation Evidence

- `python -m ruff check platform/services/c2-api/xero_c2/file_transfers.py platform/tests/unit/test_c2_api.py`
- `python -m pytest platform/tests/unit/test_c2_api.py -k "file_transfer"`
- `docker run --rm -v "${PWD}:/workspace" -w /workspace/platform/beacons/go golang:1.26 go test ./internal/filebrowser ./internal/beacon`
- `python platform/scripts/ci.py frontend-lint`
- `python platform/scripts/ci.py frontend-build`
- `python platform/scripts/ci.py frontend-test`
- `python platform/scripts/ci.py backend-unit`
- `python platform/scripts/ci.py openapi-check`
- `npm --prefix platform/frontend run test:e2e -- e2e/f0029-file-transfer.spec.ts` with `PLAYWRIGHT_BASE_URL=http://localhost:3000`, `PLAYWRIGHT_C2_BASE_URL=http://localhost:8001`, and `C2_CONNECT_PASSWORD=c2_password`
- Rebuilt and recreated C2 API stack; `/ready` reported Postgres, Redis, and artifact store healthy.
- Rebuilt and recreated the frontend container; BFF `/ready` and C2 `/ready` were healthy before the final live Playwright run.

## Maintainability Review

- File-transfer orchestration is isolated in `xero_c2/file_transfers.py`, with REST/session-websocket routing kept in `main.py` and `sessions.py`.
- Beacon filesystem behavior is isolated in the Go file-browser manager, while beacon agent code only maps encrypted `SESSION_DATA` transfer operations.
- Frontend API calls are centralized in `api.ts`; the file-browser panel owns operator workflow state and uses a compact retry affordance for resumable failed uploads.
- No additional refactor round is required for F0029. A future extraction of the file-browser panel into smaller components would be reasonable if more host file actions are added.

## Residual Notes

- `python platform/scripts/ci.py backend-lint` still fails on unrelated pre-existing lint debt in older migrations and C2 dashboard/portscan/scan_jobs/serviceenum modules; touched F0029 backend files pass `ruff`.
