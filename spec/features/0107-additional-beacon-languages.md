# F0107: Additional Beacon Languages

## Metadata
| Field | Value |
|---|---|
| ID | F0107 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0011, F0015 |

## Summary
Beacon implementations in Rust, C#, and C++ sharing the same binary protocol contract as the Go MVP beacon, with cross-language test vector compatibility.

## Requirements
- Rust beacon: memory safety, no runtime dependencies
- C# beacon: .NET 8 self-contained Windows deployment
- C++ beacon: maximum control, CMake cross-compile
- All languages pass shared protocol test vector suite
- Language selectable in beacon generation UI

## Stages

### Stage 1: Rust beacon
**Goal:** platform/beacons/rust/ with tokio async runtime.
**Acceptance Criteria:**
- [ ] Rust beacon passes all protocol test vectors
- [ ] Cross-compile for linux/musl and windows-gnu
- [ ] Binary size under 5MB stripped

### Stage 2: C# beacon
**Goal:** platform/beacons/csharp/ .NET 8 self-contained.
**Acceptance Criteria:**
- [ ] C# beacon passes protocol test vectors
- [ ] Single-file publish for windows-x64
- [ ] No .NET runtime install required on target

### Stage 3: C++ beacon
**Goal:** platform/beacons/cpp/ with CMake build.
**Acceptance Criteria:**
- [ ] C++ beacon passes protocol test vectors
- [ ] Static linking option for minimal dependencies
- [ ] Build targets linux-x64 and windows-x64

## Feature Acceptance Criteria

- [ ] Rust, C#, and C++ beacons register and complete echo task in lab
- [ ] All language beacons pass shared protocol test vector CI job
- [ ] Beacon generation UI offers language selection with build artifacts

## Test Plan

### Unit Tests
- [ ] test_rust_protocol_vectors
- [ ] test_csharp_protocol_vectors
- [ ] test_cpp_protocol_vectors
- [ ] test_go_rust_vector_compatibility
- [ ] test_beacon_language_metadata_in_registration

### System / Integration Tests
- [ ] Deploy Rust beacon; register and complete port scan task
- [ ] Deploy C# beacon on Windows lab VM; shell session works
- [ ] All language beacons coexist in same operator session

### Playwright Tests
- [ ] Beacon generation dialog offers Go, Rust, C#, C++ options
- [ ] Download Rust beacon artifact; file present and non-zero size
- [ ] Beacon list shows language badge per registered beacon
