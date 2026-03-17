# ADR-002: Idempotent Message Processing

## Status

**Accepted** — 2026-03-17

## Context

In a distributed messaging system, messages can be delivered more than once due to:

- Worker crashes mid-processing
- SQS visibility timeout expiration (message redelivered)
- Network retries
- Consumer acknowledgment failures

Without idempotency, duplicate alerts would be created, This breaks downstream aggregation and provides wrong fraud scores.

## Decision

**Implement the Idempotency Pattern: Track processed transactions per rule using a `processed_events` table.**

### Implementation

```sql
CREATE TABLE processed_events (
    transaction_id UUID,
    rule_name VARCHAR(50),
    UNIQUE(transaction_id, rule_name)
);
```

### Code Pattern (Decorator)

```python
@idempotent_worker(rule_name="HIGH_AMOUNT_RULE")
async def handle_amount_rule(transaction_id: str, amount: float) -> bool:
    # Decorator checks: Is (transaction_id, "HIGH_AMOUNT_RULE") in processed_events?
    # If yes: Skip execution, return True (message already processed)
    # If no: Execute rule, store alert, mark as processed
    ...
```

### Workflow

1. **First delivery**: Transaction A arrives
   - Check: Is (A, AMOUNT_RULE) in processed_events? **No**
   - Execute rule logic, create alert
   - Insert (A, AMOUNT_RULE) into processed_events
   - Return True (safe to delete from SQS)

2. **Retry delivery**: Same message redelivered
   - Check: Is (A, AMOUNT_RULE) in processed_events? **Yes**
   - Skip execution silently
   - Return True (safe to delete from SQS)

Result: **Only 1 alert, not 3** ✅

## Consequences

### Benefits ✅

- **Exactly-once semantics**: Despite re-deliveries, each rule evaluates transaction once
- **No duplicate alerts**: Fraud scores are accurate
- **At-most-once for SQS deletion**: Safe to call `delete_message()` after rule execution
- **Simple implementation**: Single @decorator, one table

### Trade-Offs ⚠️

- **Database overhead**: Extra query to check processed_events for every message
- **Race condition window**: Tiny gap between "check exists" and "insert" could allow 2 simultaneous executions
  - **Mitigated by**: UNIQUE constraint; 2nd insert fails, caught in exception handler
- **Processed_events grows unbounded**: Over 1 year, 100K+ transactions = millions of rows
  - **Mitigation**: Archive/delete old processed_events after retention period

### Performance Impact

- **Query cost**: 1 SELECT before processing (indexed by transaction_id, rule_name)
  - ~1ms per check
  - Negligible at scale
- **Storage**: ~50 bytes per unique (transaction_id, rule_name) pair
  - 10M transactions × 3 rules = 30M rows = ~1.5GB (acceptable)

## Alternatives Considered

### 1. Deduplication via SQS Message Deduplication ID

**Rejected** — FIFO queues with deduplication only work within 5-minute window. Our system needs month-long deduplication.

### 2. Distributed Locking (Redis)

```python
while not redis.set_nx(f"lock:{tx_id}:{rule}"):
    time.sleep(0.1)  # Wait for lock
```

**Rejected** — Adds external dependency (Redis). Database constraint is simpler and sufficient for the purpose of this project.

### 3. Event Sourcing (Store all events, replay to get state)

**Rejected** — Overkill for this use case. Idempotency + UNIQUE constraints is simpler.

### 4. No Deduplication (Accept Duplicates)

**Rejected** — Would require aggregator to deduplicate alerts (more complex), fraud scores would be wrong.

## Testing

### Unit Test: First Execution

```python
async def test_first_message_processed():
    await handle_amount_rule("tx-123", 60000.0)
    # Assert: FraudAlert created in database
    # Assert: (tx-123, AMOUNT_RULE) in processed_events
```

### Unit Test: Retry Handling

```python
async def test_duplicate_message_skipped():
    await handle_amount_rule("tx-123", 60000.0)  # First: processes
    await handle_amount_rule("tx-123", 60000.0)  # Retry: skips
    # Assert: Only 1 FraudAlert (not 2)
```

## Monitoring

Monitor:

- `fraud_message_processing_errors_total[error_category="duplicate"]` — If high, idempotency isn't working
