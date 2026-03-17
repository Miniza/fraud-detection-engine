# Architecture Decision Records (ADRs)

This directory contains the Architecture Decision Records (ADRs) for the Fraud Detection Engine. These ADRs document important architectural decisions, the context in which they were made, and the trade-offs considered.

## Format

Each ADR follows the standard format:

- **Title**: Short, descriptive name
- **Status**: Accepted, Proposed, Deprecated, Superseded
- **Context**: The problem being solved
- **Decision**: What was chosen and why
- **Consequences**: Benefits and trade-offs
- **Alternatives Considered**: Other options evaluated

## Index

1. [ADR-001: Fan-Out Messaging Architecture](001-fan-out-messaging.md)
2. [ADR-002: Idempotent Message Processing](002-idempotent-processing.md)
3. [ADR-003: Circuit Breaker for Database Resilience](003-circuit-breaker-pattern.md)
4. [ADR-004: Event-Driven Rule Workers](004-event-driven-workers.md)
5. [ADR-005: Prometheus Metrics and Observability](005-observability-strategy.md)
6. [ADR-006: Outbox Pattern Evaluation](006-outbox-pattern-evaluation.md)

## Decision Log

| ADR | Title                                   | Status   | Date       |
| --- | --------------------------------------- | -------- | ---------- |
| 001 | Fan-Out Messaging Architecture          | Accepted | 2026-03-17 |
| 002 | Idempotent Message Processing           | Accepted | 2026-03-17 |
| 003 | Circuit Breaker for Database Resilience | Accepted | 2026-03-17 |
| 004 | Event-Driven Rule Workers               | Accepted | 2026-03-17 |
| 005 | Prometheus Metrics and Observability    | Accepted | 2026-03-17 |
| 006 | Outbox Pattern Evaluation               | Proposed | 2026-03-17 |
