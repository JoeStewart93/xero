# F0029: File Transfer

## Metadata
| Field | Value |
|---|---|
| ID | F0029 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 4 |
| Depends on | F0016, F0015, F0015.01-AMD |

## Summary
Upload and download files between operator workstation and beacon filesystem via chunked transfer protocol with integrity verification and progress tracking.

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
- [ ] Transfer init frame includes filename, size, sha256, direction
- [ ] Chunks numbered with 1MB default chunk size
- [ ] ACK per chunk; NACK triggers retransmit

### Stage 2: Backend orchestration
**Goal:** Task modules builtin.upload and builtin.download.
**Acceptance Criteria:**
- [ ] Upload task stores operator file in temp storage then streams to beacon
- [ ] Download task reassembles beacon chunks into downloadable artifact
- [ ] Transfer progress published via WebSocket events

### Stage 3: Transfer UI
**Goal:** File picker upload and download buttons in file browser.
**Acceptance Criteria:**
- [ ] Upload button in file browser uploads to current directory
- [ ] Download button on file row saves to operator machine
- [ ] Progress bar shows chunk percentage during transfer

## Feature Acceptance Criteria

- [ ] 100MB file upload completes with matching SHA-256 on beacon disk
- [ ] Interrupted upload resumes from last ACK without re-uploading prior chunks
- [ ] Downloaded file matches on-beacon source file hash

## Test Plan

### Unit Tests
- [ ] test_chunk_hash_verification
- [ ] test_upload_resume_from_chunk_n
- [ ] test_download_reassembly
- [ ] test_max_file_size_rejected
- [ ] test_nack_retransmit

### System / Integration Tests
- [ ] Upload test file; verify on beacon filesystem via file browser
- [ ] Download file from beacon; hash matches source
- [ ] Simulate network drop mid-upload; resume completes successfully

### Playwright Tests
- [ ] Upload file via file browser; progress bar reaches 100%
- [ ] Download file from beacon row; browser saves file
- [ ] Transfer failure shows retry option with resume
