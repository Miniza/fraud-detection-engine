# ADR-004: Event-Driven Rule Workers

## Status

**Accepted** — 2026-03-17

## Context

Fraud rule workers need to:

1. **Continuously run** (24/7) awaiting incoming transactions
2. **Process independently** (amount rule shouldn't know about velocity rule)
3. **Scale separately** (deploy 10 amount workers but 2 blacklist workers)
4. **Start gracefully** (wait for SQS queue to exist before processing)

Architectural approaches:

- **Event-Driven**: Workers continuously listen to queues, process immediately

## Decision

**Implement Event-Driven Workers using SQS Long Polling.**

```python
async def process_amount_rule():
    sqs = get_boto_client("sqs")
    queue_url = sqs.get_queue_url(QueueName="amount-queue")

    while True:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20
        )

        for msg in response.get("Messages", []):
            await handle_amount_rule(msg)
            sqs.delete_message(QueueUrl, msg["ReceiptHandle"])
```

### Start-Up Sequence

```
Worker Container Starts
    ↓
Wait for SQS queue to become available
    ↓
Load initial configuration (blacklist, thresholds)
    ↓
Enter listening loop (process messages forever)
```

## Consequences

### Benefits ✅

- **Near real-time processing**: Fraud detected within 100-200ms (not batched every 5 minutes)
- **Efficient resource usage**: Workers sleep during long polling (no busy-waiting)
- **Horizontal scalability**: Spin up 2nd amount worker; messages auto-distribute via SQS
- **Graceful degradation**: If 1 worker crashes, others continue (SQS redistributes messages)
- **Observability**: Can monitor queue depth to detect bottlenecks

### Trade-Offs ⚠️

- **Constant resource usage**: Worker always running (vs batch job that only runs 5 min/hour)
  - **Cost**: ~1-2 vCPU per worker container
  - **Mitigation**: Minimal Python app; mostly I/O bound (waiting on SQS/DB)
- **Message visibility timeout**: If worker crashes, message invisible for 30s before SQS redelivers
  - **Mitigation**: Set timeout to match expected processing time (~5s)
- **Coordated shutdown complexity**: Must gracefully drain in-flight messages on container stop
  - **Mitigation**: Docker `stop_grace_period: 10s` gives time to finish

### Resource Requirements

Per worker process:

- **Memory**: ~50MB (Python + asyncio)
- **CPU**: <100m idle (polling), ~500m during processing
- **Network**: Low (10-100 requests/sec to SQS)

For 10M transactions/day @ 1000 tx/sec:

- **Amount workers**: 2-3 (can process ~5K tx/sec)
- **Velocity workers**: 2 (must hit DB; slower)
- **Blacklist workers**: 1 (fast; in-memory cache)

## Alternatives Considered

### 1. Batch Processing (Scheduled Job)

```
Cron: Every 5 minutes → Pull 100 transactions → Evaluate rules → Sleep
```

**Rejected** — Adds 0-5 minute latency. User waits 5 minutes to know if transaction is fraud. Unacceptable.

### 2. Synchronous Processing (API Blocks Until Rules Complete)

```
POST /transactions → Evaluate rules (blocking) → Return result
```

**Rejected** — User must wait 200ms+ for API response. Scales poorly (thread pool limited).

### 3. Lambda Functions (AWS Serverless)

```
SQS Message → Trigger Lambda → Run rule → Exit
```

**Rejected** — Cold start (3-5s) makes latency unacceptable. Also, no persistent connections to DB. Overkill for steady-state load.

## Shutdown Behavior

When `docker stop` is called:

```
1. Container receives SIGTERM
2. Worker finishes in-flight message (up to 10s grace period)
3. Doesn't pull new messages from SQS
4. Container exits cleanly
5. Docker marks container as stopped
6. Orchestrator (k8s/swarm) spawns replacement

Queue never loses messages: Unfinished messages stay in SQS.
```

## Monitoring

Track:

- `fraud_sqs_queue_depth[queue_name="amount-queue"]` — Is queue backing up?
- `fraud_rule_latency_seconds[rule_name="amount_rule"]` — How long to evaluate?
- `fraud_worker_health[worker_name="amount_rule_worker"]` — Is worker alive?

If queue depth grows → scale workers up. If latency spikes → investigate slowness.
