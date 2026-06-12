# F0058: Extended Banner Grabbing

## Metadata
| Field | Value |
|---|---|
| ID | F0058 |
| Priority | P0 |
| Status | Planned |
| MVP Phase | 3 |
| Depends on | F0023, F0069 |

## Summary
Extended service banner extraction beyond F0023 service enumeration. Probes common services (FTP, SSH, SMTP, databases, message queues) for version information and configuration details. Works from scanner service or beacon.

## Requirements
- Banner grabbing for common services
- Service-specific probes and commands
- Version extraction from banners
- Support for scanner service and beacon execution
- Timeout handling per probe
- Integration with service enumeration (F0023)

## Supported Services

| Service | Default Port | Probe Method |
| :--- | :--- | :--- |
| SSH | 22 | TCP connect, parse banner |
| FTP | 21 | SYST command |
| Telnet | 23 | TCP connect |
| SMTP | 25 | EHLO command |
| POP3 | 110 | CAPA or CAPABILITY |
| IMAP | 143 | CAPABILITY command |
| MySQL | 3306 | Handshake packet |
| PostgreSQL | 5432 | Connection info packet |
| MongoDB | 27017 | ismaster command |
| Redis | 6379 | INFO command |
| RabbitMQ | 15672 | HTTP API probe |
| Kafka | 9092 | Broker metadata request |
| Elasticsearch | 9200 | HTTP GET / |
| Memcached | 11211 | stats command |
| CouchDB | 5984 | HTTP GET / |

## Module Arguments

`python
{
    \"targets\": [\"192.168.1.100:22\", \"192.168.1.100:3306\"],
    \"services\": [\"ssh\", \"ftp\", \"smtp\", \"mysql\", \"postgresql\", \"mongodb\", \"redis\"],
    \"timeout_ms\": 5000,
    \"execution_target\": \"auto\"
}
`

## Result Schema

`json
{
    \"target\": \"192.168.1.100\",
    \"scan_time\": \"2024-01-15T10:30:00Z\",
    \"services\": [
        {
            \"port\": 22,
            \"service\": \"ssh\",
            \"banner\": \"SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5\",
            \"version\": \"8.2p1\",
            \"product\": \"OpenSSH\",
            \"os_hint\": \"Ubuntu\",
            \"extra_info\": \"protocol 2.0\"
        },
        {
            \"port\": 3306,
            \"service\": \"mysql\",
            \"banner\": \"5.7.33-0ubuntu0.20.04.1\",
            \"version\": \"5.7.33\",
            \"product\": \"MySQL\",
            \"auth_plugin\": \"caching_sha2_password\",
            \"protocol_version\": 10
        },
        {
            \"port\": 6379,
            \"service\": \"redis\",
            \"banner\": \"Redis server v=6.0.16\",
            \"version\": \"6.0.16\",
            \"product\": \"Redis\",
            \"redis_version\": \"6.0.16\",
            \"os\": \"Linux 5.4.0-42-generic x86_64\",
            \"memory_used_human\": \"1.00K\",
            \"connected_clients\": 1
        },
        {
            \"port\": 9200,
            \"service\": \"elasticsearch\",
            \"banner\": \"{\\\"version\\\":{\\\"number\\\":\\\"7.10.0\\\"...}}\",
            \"version\": \"7.10.0\",
            \"product\": \"Elasticsearch\",
            \"distribution\": \"default\",
            \"build_hash\": \"unknown\"
        }
    ],
    \"summary\": {
        \"total_services\": 4,
        \"successful_probes\": 4,
        \"failed_probes\": 0
    }
}
`

## Stages

### Stage 1: Banner Grab Module Backend
**Goal:** Register banner_grab module with schema.
**Acceptance Criteria:**
- [ ] Module registered as uiltin.recon.banner_grab
- [ ] Args validation for targets, services
- [ ] Service probe registry
- [ ] Module metadata exposed in /api/v1/modules

### Stage 2: Service Probes
**Goal:** Implement service-specific probes.
**Acceptance Criteria:**
- [ ] SSH banner grab
- [ ] FTP banner grab
- [ ] SMTP banner grab
- [ ] Database service probes
- [ ] Message queue probes

### Stage 3: Version Parsing
**Goal:** Extract version from banners.
**Acceptance Criteria:**
- [ ] Version regex patterns per service
- [ ] Product identification
- [ ] OS hint extraction
- [ ] Extra info parsing

### Stage 4: Integration
**Goal:** Link with service enumeration.
**Acceptance Criteria:**
- [ ] Results enrich F0023 data
- [ ] Service assets updated
- [ ] Version-based CVE matching prep

## Feature Acceptance Criteria

- [ ] All service probes return accurate banners
- [ ] Version parsing works for common services
- [ ] Timeout handling prevents hangs
- [ ] Results enrich service enumeration
- [ ] Works from scanner service and beacon

## Test Plan

### Unit Tests
- [ ] test_banner_grab_args_validation
- [ ] test_ssh_banner_parsing
- [ ] test_mysql_handshake_parsing
- [ ] test_redis_info_parsing
- [ ] test_version_extraction_regex

### System / Integration Tests
- [ ] SSH banner grabbed from lab server
- [ ] MySQL version extracted correctly
- [ ] Redis INFO parsed correctly
- [ ] Elasticsearch version extracted
- [ ] Timeout handled for unresponsive services

### Playwright Tests
- [ ] Banner Grab module visible in Recon module browser
- [ ] Service selection checkboxes available
- [ ] Submit task with valid targets
- [ ] Results show service versions
- [ ] Product identification displayed

## Service Probe Implementations

`python
import socket
import struct

def grab_ssh_banner(host: str, port: int = 22, timeout: int = 5000) -> dict:
    \"\"\"Grab SSH banner.\"\"\"
    try:
        with socket.create_connection((host, port), timeout=timeout/1000) as sock:
            banner = sock.recv(1024).decode('utf-8', errors='ignore')

            # Parse SSH banner: SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5
            if banner.startswith(\"SSH-\"):
                parts = banner.strip().split(\"-\")
                if len(parts) >= 3:
                    version_part = parts[2]
                    return {
                        \"port\": port,
                        \"service\": \"ssh\",
                        \"banner\": banner.strip(),
                        \"version\": extract_version(version_part),
                        \"product\": \"OpenSSH\",
                        \"os_hint\": extract_os_hint(version_part),
                    }
    except Exception:
        pass

    return {\"port\": port, \"service\": \"ssh\", \"error\": \"Connection failed\"}

def grab_mysql_banner(host: str, port: int = 3306, timeout: int = 5000) -> dict:
    \"\"\"Grab MySQL handshake banner.\"\"\"
    try:
        with socket.create_connection((host, port), timeout=timeout/1000) as sock:
            # Read handshake packet
            data = sock.recv(1024)

            if len(data) >= 9:
                protocol_version = data[0]
                # Version string starts at offset 9, null-terminated
                version_end = data.find(b'\\x00', 9)
                if version_end > 9:
                    version = data[9:version_end].decode('utf-8', errors='ignore')
                    return {
                        \"port\": port,
                        \"service\": \"mysql\",
                        \"banner\": version,
                        \"version\": extract_version(version),
                        \"product\": \"MySQL\",
                        \"protocol_version\": protocol_version,
                    }
    except Exception:
        pass

    return {\"port\": port, \"service\": \"mysql\", \"error\": \"Connection failed\"}

def grab_redis_banner(host: str, port: int = 6379, timeout: int = 5000) -> dict:
    \"\"\"Grab Redis INFO.\"\"\"
    try:
        with socket.create_connection((host, port), timeout=timeout/1000) as sock:
            sock.sendall(b\"INFO\\r\\n\")
            response = sock.recv(8192).decode('utf-8', errors='ignore')

            # Parse INFO response
            info = {}
            for line in response.split('\\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key] = value

            return {
                \"port\": port,
                \"service\": \"redis\",
                \"banner\": info.get(\"redis_version\", \"unknown\"),
                \"version\": info.get(\"redis_version\"),
                \"product\": \"Redis\",
                \"redis_version\": info.get(\"redis_version\"),
                \"os\": info.get(\"os\"),
                \"memory_used_human\": info.get(\"used_memory_human\"),
                \"connected_clients\": int(info.get(\"connected_clients\", 0)),
            }
    except Exception:
        pass

    return {\"port\": port, \"service\": \"redis\", \"error\": \"Connection failed\"}

def grab_smtp_banner(host: str, port: int = 25, timeout: int = 5000) -> dict:
    \"\"\"Grab SMTP banner.\"\"\"
    try:
        with socket.create_connection((host, port), timeout=timeout/1000) as sock:
            banner = sock.recv(1024).decode('utf-8', errors='ignore')

            # Send EHLO
            sock.sendall(f\"EHLO scanner\\r\\n\".encode())
            ehlo_response = sock.recv(4096).decode('utf-8', errors='ignore')

            return {
                \"port\": port,
                \"service\": \"smtp\",
                \"banner\": banner.strip(),
                \"ehlo\": ehlo_response.strip(),
                \"supports_tls\": \"STARTTLS\" in ehlo_response,
                \"supports_auth\": \"AUTH\" in ehlo_response,
            }
    except Exception:
        pass

    return {\"port\": port, \"service\": \"smtp\", \"error\": \"Connection failed\"}

def extract_version(version_string: str) -> str:
    \"\"\"Extract version number from string.\"\"\"
    import re
    match = re.search(r'\\d+\\.\\d+(?:\\.\\d+)?', version_string)
    return match.group(0) if match else version_string

def extract_os_hint(version_string: str) -> str | None:
    \"\"\"Extract OS hint from version string.\"\"\"
    os_hints = [\"Ubuntu\", \"Debian\", \"CentOS\", \"RHEL\", \"Fedora\", \"SUSE\"]
    for os_name in os_hints:
        if os_name in version_string:
            return os_name
    return None
`

---

*End of Document*
