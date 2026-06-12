# F0222: C2 Resilience & Redundancy

## Metadata
| Field | Value |
|---|---|
| ID | F0222 |
| Priority | High |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0205 |

## Summary
Multi-C2 server configuration with automatic failover, DNS-based C2 rotation, and connection health monitoring for production-grade reliability.

## Requirements
- Primary/backup C2 server configuration
- DNS TXT record queries for C2 updates
- Dead peer detection and automatic failover
- Connection quality scoring
- Encoded C2 URL updates via heartbeat

## Multi-C2 Configuration

```json
{
  "c2_servers": [
    {"url": "wss://primary.c2.com", "priority": 1, "weight": 0.7},
    {"url": "wss://backup.c2.com", "priority": 2, "weight": 0.2},
    {"url": "http://fallback.c2.com:8080", "priority": 3, "weight": 0.1}
  ],
  "failover": {
    "health_check_interval": 30,
    "max_failures": 3,
    "retry_backoff": [1000, 5000, 10000, 30000]
  }
}
```

## DNS-Based C2 Rotation

```c
// Query DNS TXT record for C2 updates
char *query_dns_c2_update(const char *domain) {
    char query[256];
    sprintf(query, "c2update.%s", domain);

    char *txt_record = dns_query_txt(query);
    if (txt_record) {
        // Base64 decode C2 URL
        return base64_decode(txt_record);
    }

    return NULL;
}
```

## Connection Health Monitoring

```c
typedef struct {
    char *url;
    int priority;
    double weight;
    int consecutive_failures;
    double latency_ms;
    double packet_loss;
    time_t last_success;
    time_t last_failure;
} c2_health_t;

void update_c2_health(c2_health_t *c2, bool success, double latency) {
    if (success) {
        c2->consecutive_failures = 0;
        c2->last_success = time(NULL);
        c2->latency_ms = latency;
    } else {
        c2->consecutive_failures++;
        c2->last_failure = time(NULL);
    }

    // Trigger failover if needed
    if (c2->consecutive_failures >= MAX_FAILURES) {
        trigger_c2_failover(c2);
    }
}
```

## Stages

### Stage 1: Multi-C2 Configuration
- [ ] Primary/backup C2 server config
- [ ] Priority and weight-based selection
- [ ] Health scoring algorithm

### Stage 2: DNS-Based Rotation
- [ ] TXT record queries for C2 updates
- [ ] DNS round-robin failover
- [ ] Cached C2 addresses

### Stage 3: Connection Health
- [ ] Dead peer detection
- [ ] Connection quality scoring
- [ ] Automatic failover logic

### Stage 4: Configuration Updates
- [ ] Push C2 URL updates via heartbeat
- [ ] Encoded C2 URLs (Base64, XOR)
- [ ] Signed configuration verification

## Feature Acceptance Criteria
- [ ] Automatic failover to backup C2 on primary failure
- [ ] DNS TXT record updates C2 URL successfully
- [ ] Connection health scoring accurate
- [ ] C2 URL updates received via heartbeat

## Test Plan

### Unit Tests
- [ ] test_c2_selection_algorithm
- [ ] test_dns_txt_query_parsing
- [ ] test_health_score_calculation
- [ ] test_failover_trigger

### System Tests
- [ ] Kill primary C2; verify failover to backup
- [ ] Update DNS TXT; verify C2 URL update
- [ ] Simulate high latency; verify scoring

### Playwright Tests
- [ ] Configure multiple C2 servers in UI
- [ ] View C2 health status
- [ ] Trigger manual failover
