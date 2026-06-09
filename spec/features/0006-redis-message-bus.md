# F0006: Redis Message Bus

## Metadata
| Field | Value |
|---|---|
| ID | F0006 |
| Priority | P0 |
| Status | Complete |
| MVP Phase | 1 |
| Depends on | F0001, F0004 |

## Summary
Redis client integration for task queues, pub/sub real-time events, session cache, and rate limiting.

## Current Implementation Note
F0006 is complete as the Redis foundation. Both backend roles have async Redis client setup, startup ping/degraded status handling, JSON queue helpers, pub/sub helpers, JSON cache helpers, and Redis-backed per-operator rate limiting for protected API routes. F0008 now uses the pub/sub foundation for operator WebSocket delivery; real task APIs and user-visible throttle/status UI remain owned by later feature specs.

## Requirements
- Redis for task queue, pub/sub, session cache, rate limiting
- Async Redis client compatible with FastAPI
- Graceful handling of Redis unavailability

## Stages

### Stage 1: Client setup
**Goal:** Configure async Redis connection pool.
**Acceptance Criteria:**
- [x] Redis URL from environment
- [x] Connection tested on startup
- [x] Health check reports redis status

### Stage 2: Queue primitives
**Goal:** Implement list/stream based queue helpers.
**Acceptance Criteria:**
- [x] enqueue/dequeue task helpers
- [x] Task payload JSON serialized
- [x] Failed dequeue returns None without error

### Stage 3: Pub/sub channel
**Goal:** Publish and subscribe helpers for events.
**Acceptance Criteria:**
- [x] publish_event(channel, payload) helper
- [x] subscribe pattern for operator notifications
- [x] Rate limiter using Redis counters

## Feature Acceptance Criteria

- [x] Redis connectivity verified on backend startup
- [x] Queue and pub/sub primitives available to task and websocket modules
- [x] Rate limiter blocks excessive requests per operator

## Test Plan

### Unit Tests
- [x] test_redis_enqueue_dequeue round-trip
- [x] test_pubsub_publish_receive
- [x] test_rate_limiter blocks after threshold

### System / Integration Tests
- [x] Enqueue task in Redis; dequeue from second process
- [x] Pub/sub message received by subscriber within 1s

### Playwright Tests
- [x] Not applicable for F0006 backend foundation; system status UI remains with F0007/F0024.
- [x] Not applicable for F0006 backend foundation; user-visible throttle messaging remains with later UI features.
