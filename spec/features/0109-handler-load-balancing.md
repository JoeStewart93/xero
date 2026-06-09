# F0109: Handler Load Balancing

## Metadata
| Field | Value |
|---|---|
| ID | F0109 |
| Priority | P1 |
| Status | Planned |
| MVP Phase | 5 |
| Depends on | F0038, F0039, F0010 |

## Summary
Production handler pool management across multiple external beacon handlers using round-robin, least-connections, and weighted assignment with health checks, draining, and automatic beacon migration when a handler goes unhealthy.

## Requirements
- Load balancer distributes beacons across healthy handlers
- Algorithms: round-robin, least-connections, weighted
- Health check removes unhealthy handlers from pool
- Failover marks affected beacons for migration to healthy handlers
- Draining handler stops receiving new assignments while existing beacons reconnect or migrate
- Nginx or Kubernetes Ingress configuration templates provided

## Stages

### Stage 1: Handler pool registry
**Goal:** C2 tracks handler pool with health scores.
**Acceptance Criteria:**
- [ ] handler_pool table with weight, health_score, algorithm
- [ ] Health check ping every 30s; score decay on miss
- [ ] Unhealthy handler removed from assignment pool
- [ ] Draining handler remains visible but receives no new assignments

### Stage 2: Assignment algorithm
**Goal:** Assign beacons to handlers by selected algorithm.
**Acceptance Criteria:**
- [ ] Round-robin cycles through healthy handlers
- [ ] Least-connections assigns to handler with fewest beacons
- [ ] Assignment returned in beacon registration response
- [ ] Assignment can choose embedded C2 handler when no external handler is healthy

### Stage 3: Failover and beacon migration
**Goal:** Move affected beacons away from failed handlers.
**Acceptance Criteria:**
- [ ] Handler failure emits operator-visible failover event
- [ ] Beacons connected through failed handler are marked for reassignment
- [ ] Reconnected beacons receive healthy handler assignment

### Stage 4: Ingress templates
**Goal:** Nginx and K8s Ingress config for handler LB.
**Acceptance Criteria:**
- [ ] nginx.conf template for TLS passthrough to handler pool
- [ ] K8s Ingress manifest with handler service endpoints
- [ ] Documentation for HA handler deployment topology

## Feature Acceptance Criteria

- [ ] 10 beacons distributed across 3 handlers within 20% balance tolerance
- [ ] Handler failure triggers beacon migration/reassignment within 60s
- [ ] Nginx LB template passes health check integration test

## Test Plan

### Unit Tests
- [ ] test_round_robin_assignment
- [ ] test_least_connections_assignment
- [ ] test_health_check_removes_unhealthy
- [ ] test_failover_beacon_migration
- [ ] test_draining_handler_excluded_from_new_assignments
- [ ] test_weighted_distribution

### System / Integration Tests
- [ ] Register 10 beacons; verify distribution across handler pool
- [ ] Kill one handler; affected beacons reconnect to healthy handlers
- [ ] Nginx LB routes beacon traffic to correct handler backend

### Playwright Tests
- [ ] Handler pool settings shows distribution chart per handler
- [ ] Unhealthy handler shows red status in handler list
- [ ] Failover event logged in infrastructure events panel
