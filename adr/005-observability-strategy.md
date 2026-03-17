# ADR-005: Prometheus Metrics and Observability

## Status

**Accepted** — 2026-03-17

## Context

A distributed fraud detection system requires visibility into:

- **Operational health**: Are workers alive? Is the database reachable?
- **Performance**: How fast are rules evaluated? Is aggregator causing bottlenecks?
- **Errors**: What types of failures occur? How often?
- **Business metrics**: How many transactions are approved/rejected?

Without observability, operators are blind:

- Queue backs up → Why? (slow workers? DB down? Network issues?)
- Fraud detection latency increases → Which rule is slow?
- Workers crash → How many? Why?

## Decision

**Implement Prometheus metrics across all system components.**

### Metrics Categories

#### 1. Business Metrics (4xx metrics)

```
fraud_tx_processed_total{service="amount_rule", status="flagged"}
fraud_tx_processed_total{service="amount_rule", status="cleared"}
```

→ Track: How many transactions flagged per rule?

#### 2. Performance Metrics (Latency)

```
fraud_rule_latency_seconds{rule_name="amount_rule"}  # Histogram
fraud_api_request_latency_seconds{method="POST", endpoint="/transactions"}
```

→ Track: Are rules getting slower? Why?

#### 3. Infrastructure Metrics (Health)

```
fraud_sqs_queue_depth{queue_name="amount-queue"}
fraud_worker_health{worker_name="amount_rule_worker"}  # 1=healthy, 0=down
fraud_db_pool_connections{pool_name="postgres"}
```

→ Track: Queue backing up? Workers dying? DB connections exhausted?

#### 4. Error Metrics (Failures)

```
fraud_message_processing_errors_total{queue_name="amount-queue", error_category="parsing_error"}
fraud_message_processing_errors_total{queue_name="amount-queue", error_category="circuit_breaker_open"}
fraud_message_processing_errors_total{queue_name="amount-queue", error_category="sqs_error"}
```

→ Track: What breaks most often?

### Targets

Each component exports metrics on port 9000:

- API: `http://localhost:8000/metrics`
- Amount Worker: `http://localhost:9000/metrics`
- Velocity Worker: `http://localhost:9000/metrics`
- Blacklist Worker: `http://localhost:9000/metrics`
- Aggregator: `http://localhost:9000/metrics`

Prometheus scrapes every 10 seconds:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: fraud-engine
    targets:
      - api:8000
      - worker-amount:9000
      - worker-velocity:9000
      - worker-blacklist:9000
      - worker-aggregator:9000
```

## Consequences

### Benefits ✅

- **Proactive alerting**: Can alert on queue depth > 1000 before users complain
- **Performance debugging**: Histogram latency shows "99th percentile = 500ms" or "p99 = 100ms"
- **Postmortem root cause**: "Circuit breaker opened 47 times yesterday" → Database had issues
- **Capacity planning**: Track trends over time; when to scale
- **Cost insights**: Worker CPU usage → know if downsizing is possible

### Trade-Offs ⚠️

- **Metric cardinality explosion**: If we track per-merchant, per-user → millions of unique metrics
  - **Mitigated by**: Only track aggregated metrics (service-level), not per-transaction
- **Storage overhead**: Prometheus stores ~10MB/day for this system (negligible)
- **Latency impact**: Incrementing counters adds ~1% CPU overhead (negligible)

### Alert Examples

```
# Alert if queue is backing up
alert: "SQS Amount Queue Depth High"
if: fraud_sqs_queue_depth{queue_name="amount-queue"} > 100
for: 5m

# Alert if worker is unhealthy
alert: "Amount Rule Worker Down"
if: fraud_worker_health{worker_name="amount_rule_worker"} == 0

# Alert if error rate spikes
alert: "Message Processing Errors High"
if: rate(fraud_message_processing_errors_total[5m]) > 10/second
```

## Alternatives Considered

### 1. ELK Stack (Elasticsearch, Logstash, Kibana)

**Rejected** — Overkill for this use case. Too much storage cost. Prometheus is lighter.

### 2. CloudWatch (AWS Native)

**Rejected** — Vendor lock-in. Harder to test locally. Prometheus is portable.

### 3. No Metrics (Just Logs)

**Rejected** — "Log says error happened" isn't enough. Need metrics to aggregate ("how many errors in past hour?").

## Monitoring Examples

### Dashboard: Queue Health

```
Metric: fraud_sqs_queue_depth
Expected: < 10 (messages processed rapidly)
Red alert: > 100 (messages piling up)

Interpretation:
- If high: Workers are slow or down
- Correlate with: fraud_rule_latency_seconds
- Action: Scale up workers or investigate slowness
```

### Dashboard: Rule Performance

```
Metric: fraud_rule_latency_seconds (histogram percentiles)
Expected: p50=50ms, p95=100ms, p99=200ms
Red alert: p99 > 500ms

Interpretation:
- Amount rule slow? Maybe DB query slow
- Velocity rule slow? Maybe many recent transactions
- Action: Check database metrics, investigate queries
```

### Dashboard: System Health

```
Metric: fraud_worker_health
Expected: All workers = 1
Red alert: Any worker = 0

Interpretation:
- Worker crashed or can't reach SQS
- Action: Check logs, restart pod, investigate SQS availability
```

## Testing

### Unit Test: Counter Incremented

```python
def test_error_counter_incremented():
    MESSAGE_PROCESSING_ERRORS.labels(
        queue_name="test-queue",
        error_category="test_error"
    ).inc()

    metrics = generate_latest(REGISTRY)
    assert b'fraud_message_processing_errors_total{error_category="test_error"' in metrics
```

### Integration Test: End-to-End Metrics

```python
async def test_full_flow_emits_metrics():
    # Send transaction API
    # Wait for rules to complete
    # Query Prometheus /metrics endpoint
    # Assert: fraud_tx_processed_total incremented
```
