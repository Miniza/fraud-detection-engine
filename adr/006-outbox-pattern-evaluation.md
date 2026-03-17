# ADR-006: Outbox Pattern Evaluation

## Status

**Proposed** (Deferred for future implementation) — 2026-03-17

## Context

Current system architecture has a potential failure scenario:

```
1. API saves transaction to DB: ✅ SUCCESS
2. API calls SNS.publish():    ❌ FAILS (network, SNS down)
   → Transaction in DB but never published to queue
   → Fraud rules never evaluate
   → Transaction appears fraudulent (stuck in PENDING state)
```

The Outbox Pattern solves this by decoupling the database write from the message publish:

```
1. API saves transaction + outbox entry in SAME transaction (Atomic)
2. Background worker polls outbox: Pick unpublished entries
3. Worker publishes to SNS
4. Worker marks as published (delete from outbox)
```

This guarantees "at-least-once" message delivery even if components fail.

## Decision (Deferred)

**NOT Implementing Yet.** Current system accepts the risk for the sake of simplicity and due to the purpose of the project.

### Why Deferred (Not Rejected)

1. **Risk is low for fraud detection**:
   - If SNS fails, transaction stuck in PENDING (not silently approved)
   - User sees "Processing" state; fraud team can manually review
   - SNS has 99.99% availability; outages are rare

2. **Complexity trade-off**:
   - Outbox adds: polling loop, transaction state management, cleanup jobs
   - For this scale (10M tx/day), easier to handle rare failures manually

## Failure Scenarios

### Scenario 1: SNS Down (Acceptable Risk)

**Current System:**

```
POST /transactions
  → Save to DB ✅
  → SNS.publish() ❌ (timeout)
  → API returns error
User sees: "Transaction failed (500)"
Fraud team: Manually reviews pending transaction next day
Recovery time: Hours to days
```

**With Outbox:**

```
POST /transactions
  → Save tx + outbox entry (atomic) ✅
  → API returns success
Background worker: Retries publish every 5s
Recovery time: Minutes (automatic retry)
```

**Verdict:** Outbox is better, but current system is acceptable for MVP and for the purpose of this project (recruitment...).

### Scenario 2: Worker Crashes (Already Handled)

**Current System + Idempotency:**

```
Worker processes message ✅
Worker crashes before delete ❌
SQS redelivers message after 30s
Worker process again (idempotency check prevents duplicate)
✅ No problem
```

**This scenario is already solved by ADR-002.**

### Scenario 3: Database Down (Already Handled)

**Current System + Circuit Breaker:**

```
Worker tries to write alert
DB connection fails 5 times
Circuit breaker opens
Worker rejects request (fast fail)
Message stays in SQS
DB recovers, worker comes back online
Message reprocessed ✅
```

**This scenario is already solved by ADR-003.**

## Alternative Patterns (Not Chosen)

### 1. Saga Pattern (Distributed Transactions)

**Rejected** — Overkill for this use case. Sagas handle multi-step workflows; we only have two steps (save + publish).

### 2. Event Sourcing (Append-only log)

**Rejected** — Heavy. Would require replaying all events to get current state.
