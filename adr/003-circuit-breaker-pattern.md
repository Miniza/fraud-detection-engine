# ADR-003: Circuit Breaker for Database Resilience

## Status

**Accepted** — 2026-03-17

## Context

Workers depend on PostgreSQL for:

- Reading transaction data (velocity rule)
- Writing fraud alerts
- Checking idempotency (processed_events)

If database becomes unavailable (network down, crashes, overload):

- All workers block waiting for DB connection
- Queue depth grows indefinitely
- Workers appear healthy but achieve nothing
- Recovery is slow (must wait for DB + all workers to drain backlog)

## Decision

**Implement Circuit Breaker pattern** using the `circuitbreaker` library.

```python
@circuit(
    failure_threshold=5,      # After 5 failures, open circuit
    recovery_timeout=60,      # Try again after 60s
    expected_exception=(OperationalError, DatabaseDownError)
)
async def get_resilient_db():
    # Try to get DB session
    # If fails 5x, raise CircuitBreakerError without attempting
    ...
```

## Consequences

### Benefits ✅

- **Fail fast**: Workers don't wait 30s for DB timeout; instead get error immediately
- **Reduces cascading load**: Bad requests stop piling up; gives DB time to recover
- **Observable state**: Can alert: "Circuit open on database-down; DB unreachable"
- **Limits blast radius**: Workers can implement fallback logic rather than blocking

### Trade-Offs ⚠️

- **Messages lost during outage**: While circuit is open, workers don't process messages
  - **Mitigated by**: Messages stay in SQS queue; processed once DB recovers
- **Recovery delay**: 60s timeout means 60s of no processing (by design; gives DB time)

### Availability Impact

- **Database healthy**: Zero impact; circuit always closed
- **Database down 5 minutes**:
  - 0-5s: Workers detect failure
  - 5-65s: Circuit open, workers reject requests (clean failure)
  - 65s+: Circuit half-open, attempt recovery

## Alternatives Considered

### 1. No Circuit Breaker (Retry Forever)

```python
while True:
    try:
        return await db.execute(query)
    except Exception:
        await asyncio.sleep(2)  # Retry
```

**Rejected** — Workers could hang for hours waiting for unresponsive DB. Queue grows indefinitely.

### 2. Fixed Timeout (3 Retries, Then Fail)

```python
for i in range(3):
    try:
        return await db.execute(query)
    except:
        if i == 2: raise
```

**Rejected** — Doesn't differentiate between "transient failure" and "DB is down". 3 retries = 6s delay for each down message.

### 3. Adaptive Timeout (Exponential Backoff)

```python
timeout = 1 * (2 ** attempt_count)  # 1s, 2s, 4s, 8s...
```

**Rejected** — Better, but still doesn't provide feedback to external systems. Circuit breaker is explicit.

### 4. Cache Results From Last Successful DB Query

**Rejected** — For fraud detection, stale cache could miss new blacklist entries or velocity violations.

## Implementation Details

### Resilience Configuration

```python
DB_BREAKER_CONFIG = {
    "failure_threshold": 5,           # Open after 5 failures
    "recovery_timeout": 60,           # Try recovery after 60s
    "expected_exception": (OperationalError, DatabaseDownError)
}
```

**Rationale:**

- **5 failures**: Filters out transient blips (1-2 failures); opens on sustained issues
- **60 seconds**: Enough for DB to reboot or network to recover; not too long to block users
- **Expected exceptions**: Only count expected errors; unexpected errors still crash (good for sentry alerts)

### Monitoring

Track:

- `fraud_message_processing_errors_total[error_category="circuit_breaker_open"]` — Is circuit open? Why?
- `fraud_worker_health[worker_name="X"]` → 0 if circuit open

### Fallback Strategy

Currently: **Fail** the message (SQS redelivers).

Future: Could implement **deferred processing**:

```python
except CircuitBreakerError:
    # Put message back in queue for later
    sqs.send_message(original_message)
    return False  # Don't delete from SQS
```

## Testing

### Test: Circuit Opens After Threshold

```python
# Simulate 5 DB failures
for i in range(5):
    with patch('db.execute', side_effect=OperationalError()):
        with pytest.raises(CircuitBreakerError):
            await get_resilient_db()

# Next call should fail immediately (circuit open)
with pytest.raises(CircuitBreakerError):
    await get_resilient_db()  # No DB call attempted!
```

### Test: Circuit Closes After Recovery

```python
# Open circuit (5 failures)
# Wait 60s
# Mock successful DB response
await get_resilient_db()  # Should succeed
# Circuit back to CLOSED
```
