# F0110: RabbitMQ Message Bus

## Metadata
| Field | Value |
|---|---|
| ID | F0110 |
| Priority | v2 |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0006 |

## Summary
v2 alternative message bus using RabbitMQ for task queuing and pub/sub, configurable alongside Redis with a unified queue abstraction layer in Xero C2.

## Requirements
- RabbitMQ as alternative to Redis for task queue and pub/sub
- QUEUE_BACKEND env var selects redis or rabbitmq
- Unified queue abstraction interface implemented by both backends
- RabbitMQ added to docker-compose as optional profile
- Migration guide from Redis-only to RabbitMQ deployment

## Stages

### Stage 1: Queue abstraction
**Goal:** Define MessageBus interface with Redis and RabbitMQ implementations.
**Acceptance Criteria:**
- [ ] MessageBus interface: enqueue, dequeue, publish, subscribe
- [ ] RedisMessageBus wraps existing F0006 implementation
- [ ] RabbitMQMessageBus uses AMQP exchanges and queues

### Stage 2: RabbitMQ integration
**Goal:** Implement AMQP client with connection pooling.
**Acceptance Criteria:**
- [ ] aio-pika async client integrated in FastAPI lifespan
- [ ] Task queue uses durable RabbitMQ queue per beacon
- [ ] Pub/sub uses fanout exchange for operator events

### Stage 3: Compose and migration
**Goal:** Docker Compose profile and migration documentation.
**Acceptance Criteria:**
- [ ] docker-compose --profile rabbitmq adds RabbitMQ service
- [ ] QUEUE_BACKEND=rabbitmq switches C2 to RabbitMQ backend
- [ ] Migration doc covers Redis-to-RabbitMQ cutover steps

## Feature Acceptance Criteria

- [ ] C2 runs with QUEUE_BACKEND=rabbitmq; all task flows work identically
- [ ] Operator WebSocket events delivered via RabbitMQ pub/sub
- [ ] Switching backend requires only env var change and restart

## Test Plan

### Unit Tests
- [ ] test_message_bus_interface_compliance
- [ ] test_rabbitmq_enqueue_dequeue
- [ ] test_rabbitmq_pubsub_delivery
- [ ] test_backend_selection_from_env
- [ ] test_redis_backend_still_default

### System / Integration Tests
- [ ] Start compose with rabbitmq profile; dispatch task; beacon receives
- [ ] Pub/sub event via RabbitMQ received on operator WebSocket
- [ ] Switch QUEUE_BACKEND to redis; identical task flow passes

### Playwright Tests
- [ ] Settings shows message bus backend: RabbitMQ when configured
- [ ] Task queue flows work identically with RabbitMQ backend
- [ ] Health panel shows RabbitMQ connected status
