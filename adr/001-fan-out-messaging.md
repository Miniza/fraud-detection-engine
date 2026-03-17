# ADR-001: Fan-Out Messaging Architecture

## Status

**Accepted** — 2026-03-17

## Context

The fraud detection system needs to evaluate each transaction against multiple independent fraud rules concurrently. These rules check different aspects:

- **Amount Rule**: Transaction size validation
- **Velocity Rule**: Rapid sequential transactions from same user
- **Blacklist Rule**: Known fraudulent merchants or users from a blacklist table

Key requirements:

1. Evaluate all rules in parallel (not sequentially)
2. Decouple rule workers from the API
3. Scale rule workers independently
4. Prevent rule failure from blocking others

## Decision

**Implement a fan-out messaging architecture using SNS (published events) → SQS (consumed by workers)**

## Consequences

### Benefits ✅

- **Parallel execution**: All rules evaluate simultaneously (faster fraud detection)
- **Independent scaling**: Can run 10x amount workers, 2x velocity workers via container replicas
- **Fault isolation**: If one rule crashes e.g. blacklist, other rules continue
- **Asynchronous processing**: API returns immediately; workers process in background
- **Message durability**: SQS retries handle transient failures
- **Decoupling**: Adding new rules (e.g., "Geography Rule") doesn't affect existing rules

### Trade-Offs ⚠️

- **Eventual consistency**: API returns before fraud results are in database (~50-200ms latency)
- **Operational complexity**: Must monitor 4 SQS queues + health of 4 worker types
- **Message duplication risk**: SQS can deliver same message 2x; requires idempotency (see ADR-002)
- **Cascading failures**: If database is down, **all** workers block (mitigated by circuit breaker, see ADR-003)
- **Missing message scenario**: If SNS.publish() fails after transaction is saved, fraud detection never runs - to fix the issue of dual write we propose implementing outbox pattern though not implemented yet

### Latency Impact

- **Best case**: 50ms (aggregator collects 3 alerts, updates DB)
- **Typical case**: 100-200ms (workers process, aggregator waits for slowest)
- **Worst case**: 5s (SQS visibility timeout if worker crashes)

## Alternatives Considered

### 1. Sequential Rule Evaluation

```
API → Rule 1 → Rule 2 → Rule 3 → DB
```

**Rejected** — Total latency = sum of all rule times. If one rule takes 500ms, user waits 500ms+ for API response. Doesn't scale.

### 2. Synchronous Worker Pool (Thread Executor)

```
API → [Rule Worker Thread Pool] → DB
```

**Rejected** — Worker threads are in-process; no fault isolation. One stuck thread blocks others. Can't scale separately.

### 3. Message Bus (Kafka Instead of SNS/SQS)

```
API → Kafka Topic → [Partitions] → Workers
```

**Rejected** — Kafka adds operational burden (requires broker cluster). SQS is simpler, managed by AWS. For this scale, SQS is sufficient.

## Monitoring

Monitor these metrics:

- `fraud_sqs_queue_depth` — Are messages piling up?
- `fraud_rule_latency_seconds` — Is one rule slower than others?
- `fraud_worker_health` — Are workers alive?

If queue depth grows → scale workers up. If latency spikes on one rule → investigate that worker.
