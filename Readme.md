# Real-Time Fraud Detection Engine

A **high-concurrency, event-driven fraud detection system** built with **FastAPI**, **PostgreSQL**, and **AWS SNS/SQS**.

This project demonstrates a **production-style fan-out architecture** where financial transactions are processed through multiple independent fraud detection rules **in parallel**.

The system simulates how modern financial platforms evaluate transactions using **distributed workers and asynchronous processing**.

The platform also implements **resilience and reliability patterns** such as **Idempotency** and the **Circuit Breaker Pattern** to ensure safe and fault-tolerant message processing.

---

# Architecture Overview

The system uses a **fan-out messaging pattern** to evaluate transactions across multiple fraud detection rules simultaneously.

## Processing Flow

1. **API Gateway (Producer)**
   - A FastAPI service receives transaction requests.
   - An **idempotency key** is used to prevent duplicate transaction processing.
   - The transaction event is published to an **SNS Topic**.

2. **Fan-Out Layer**
   - SNS distributes the event to multiple **SQS queues**.

3. **Fraud Rule Workers (Consumers)**

Each worker evaluates the transaction independently:

- **Amount Rule**
  - Flags unusually large transactions.

- **Velocity Rule**
  - Detects rapid repeated transactions within a short time window.

- **Blacklist Rule**
  - Checks if a merchant or user is restricted.

Each worker:

- Implements **idempotent message processing** to prevent duplicate rule evaluation.
- Uses a **circuit breaker** to protect downstream services such as the database.

4. **Aggregator Worker**

The aggregator collects results from all rule workers and determines the final transaction status.

Final outcomes:

- **APPROVED**
- **REJECTED**

The final result is stored in **PostgreSQL**.

---

# System Architecture

```
Client
   |
FastAPI API
   |
 SNS Topic
   |
+----------------------+
|      Fan-Out         |
+----------------------+
   |       |       |
   |       |       |
Amount  Velocity  Blacklist
Worker   Worker    Worker
   \       |       /
    \      |      /
       Aggregator
           |
        PostgreSQL
```

This architecture enables:

- Parallel rule execution
- Independent worker scaling
- Fault isolation
- Asynchronous processing
- Safe retries with idempotent consumers
- Resilience against downstream failures

---

# Resilience Patterns

To support **high reliability in distributed systems**, the platform implements the following patterns.

---

## Idempotency

In distributed event-driven systems, **duplicate messages can occur** due to retries, network issues, or SQS redelivery.

To ensure **exactly-once logical processing**, the system implements **idempotent consumers**.

### How It Works

- Each transaction includes a **unique transaction_id**.
- Workers check if the transaction has **already been processed** before executing rule logic.
- If a duplicate event is received, the worker **skips processing**.

### Benefits

- Prevents duplicate fraud evaluations
- Ensures safe message retries
- Supports **at-least-once delivery guarantees** from SQS

Example protection scenarios:

- Worker crashes after processing but before acknowledgement
- SQS message redelivery
- API retry sending the same transaction

---

## Circuit Breaker Pattern

The **Circuit Breaker Pattern** protects the system from cascading failures when dependent services become unavailable.

In this system, workers use a circuit breaker around **database operations and external service calls**.

### Circuit States

The circuit breaker operates in three states:

**Closed**

- Normal operation
- Requests flow normally

**Open**

- Triggered after repeated failures
- Requests fail immediately to prevent overload

**Half-Open**

- Allows limited test requests
- If successful, the circuit closes again

### Benefits

- Prevents cascading failures
- Reduces pressure on unhealthy services
- Improves overall system stability

---

# Tech Stack

| Component        | Technology               |
| ---------------- | ------------------------ |
| Language         | Python 3.11              |
| Framework        | FastAPI                  |
| Database         | PostgreSQL 16            |
| ORM              | SQLAlchemy 2.0 + Asyncpg |
| Messaging        | AWS SNS & SQS            |
| AWS Mock         | Moto Server              |
| Observability    | Prometheus + Grafana     |
| Containerization | Docker                   |
| Orchestration    | Docker Compose           |

---

# Features

- Event-driven fraud detection pipeline
- Parallel rule evaluation via SNS fan-out
- Independent worker architecture
- Aggregated fraud decision engine
- Async Python processing
- **Idempotent message processing**
- **Circuit breaker fault protection**
- System observability with Prometheus and Grafana
- Fully containerized development environment

---

# Quick Start

## Prerequisites

Install the following:

- Docker
- Docker Compose

---

## Clone the Repository

```bash
HTTPS:

git clone https://github.com/Miniza/fraud-detection-engine.git
cd fraud-detection-engine
```

```bash
SSH:

git clone git@github.com:Miniza/fraud-detection-engine.git
cd fraud-detection-engine
```

(Optional)

```bash
code .
```

---

## Start the System

Build and start all services:

```bash
docker compose up --build -d
```

This starts:

- FastAPI API
- PostgreSQL database
- SNS/SQS mock services
- Fraud rule workers
- Aggregator worker
- Prometheus
- Grafana

---

# API Documentation

## Create Transaction

Creates a transaction and sends it to the fraud detection pipeline.

### Endpoint

```
POST /transactions
```

### Request Payload

```json
{
  "user_id": "user_12345",
  "amount": 150.5,
  "currency": "ZAR",
  "merchant_id": "merch_xyz1",
  "merchant_category": "Retail"
}
```

### Response

```json
{
  "status": "accepted",
  "transaction_id": "some-uuid"
}
```

Transactions are processed **asynchronously** by background workers.

---

# Get Transaction Status

Retrieves fraud evaluation results.

### Endpoint

```
GET /transactions/{transaction_id}
```

### Path Parameter

| Parameter      | Type | Description                   |
| -------------- | ---- | ----------------------------- |
| transaction_id | UUID | Unique transaction identifier |

### Example Response

```json
{
  "transaction_id": "some-id",
  "status": "ACCEPTED",
  "fraud_summary": {
    "is_flagged": false,
    "alerts": [
      {
        "rule": "HIGH_AMOUNT_RULE",
        "reason": "Within limit"
      },
      {
        "rule": "VELOCITY_RULE",
        "reason": "Within limits"
      },
      {
        "rule": "BLACKLIST_RULE",
        "reason": "Merchant cleared"
      }
    ]
  }
}
```

### NB: IF Status appears as PENDING, You might have to wait a few seconds for the aggragator consumer to finish deciding. The Final Result will always be either APPROVED/REJECTED

---

# Simulating Fraud Scenarios

You can simulate fraud detection by sending specific transaction patterns.

---

# Amount Rule (High Transaction Amount)

Rule triggers when:

```
amount > 50,000
```

### Example Payload

```json
{
  "user_id": "user_777",
  "amount": 75000,
  "currency": "ZAR",
  "merchant_id": "merch_321",
  "merchant_category": "Electronics"
}
```

Expected Result:

```
HIGH_AMOUNT_RULE will trigger
```

---

# Blacklist Rule

Rule triggers when:

```
merchant_id = "merch_999"
```

### Example Payload

```json
{
  "user_id": "user_222",
  "amount": 200,
  "currency": "ZAR",
  "merchant_id": "merch_999",
  "merchant_category": "Retail"
}
```

Expected Result:

```
BLACKLIST_RULE will trigger
```

---

# Velocity Rule

Rule triggers when:

```
4 transactions occur within 10 minutes
```

Send the following **4 transactions quickly** using the same `user_id`.

### Transaction 1

```json
{
  "user_id": "user_velocity_test",
  "amount": 100,
  "currency": "ZAR",
  "merchant_id": "merch_101",
  "merchant_category": "Food"
}
```

### Transaction 2

```json
{
  "user_id": "user_velocity_test",
  "amount": 120,
  "currency": "ZAR",
  "merchant_id": "merch_102",
  "merchant_category": "Food"
}
```

### Transaction 3

```json
{
  "user_id": "user_velocity_test",
  "amount": 140,
  "currency": "ZAR",
  "merchant_id": "merch_103",
  "merchant_category": "Food"
}
```

### Transaction 4

```json
{
  "user_id": "user_velocity_test",
  "amount": 160,
  "currency": "ZAR",
  "merchant_id": "merch_104",
  "merchant_category": "Food"
}
```

Expected Result:

```
VELOCITY_RULE will trigger on the fourth transaction
```

---

# Observability

The system includes monitoring tools.

### FastAPI Docs

```
http://localhost:8000/docs
```

### Metrics

```
http://localhost:8000/metrics
```

### Prometheus

```
http://localhost:9090
```

### Grafana

```
http://localhost:3000
```

---

# Testing

The project includes comprehensive unit tests covering core fraud detection logic and edge cases.

## Unit Test Suite Overview

**Total Coverage: 28 unit tests**

| Module                 | Tests | Focus                                  |
| ---------------------- | ----- | -------------------------------------- |
| **Amount Rule**        | 4     | Boundary conditions, threshold testing |
| **Velocity Rule**      | 4     | Time windows, transaction counting     |
| **Blacklist Rule**     | 4     | Cache usage, merchant lookups          |
| **Idempotency**        | 5     | Deduplication of duplicate messages    |
| **Service Layer**      | 6     | CRUD operations, SNS publishing        |
| **Exception Handlers** | 5     | HTTP error codes, response formats     |

---

## Prerequisites for Running Tests

Before running tests, ensure you have:

1. **Python 3.11+** installed
2. **Dependencies installed**:

```bash
pip install -r requirements-dev.txt

or

python -m pip install -r requirements-dev.txt #If Scripts are disabled use this
```

---

## Running Unit Tests

### 1. Run All Unit Tests

```bash
pytest tests/unit/ -v

or

python -m pytest tests/unit/ -v #if scripts are disabled use this
```

Output:

```
============================= test session starts ==============================
platform <platform> -- Python 3.14.3, pytest-7.4.4, pluggy-1.6.0
collected 28 items

tests/unit/test_amount_rule.py::test_high_amount_flagged PASSED     [  3%]
tests/unit/test_amount_rule.py::test_low_amount_not_flagged PASSED  [  7%]
...
========================== 28 passed in 1.61s ==========================
```

### 2. Run Tests with Verbose Output

```bash
pytest tests/unit/ -v --tb=short
```

This shows:

- Each test name
- Pass/fail status
- Short traceback for failures

### 3. Run Tests Quietly (Summary Only)

```bash
pytest tests/unit/ -q
```

Output shows just the final summary:

```
28 passed in 1.61s
```

### 4. Run Specific Test File

```bash
# Test a specific rule
pytest tests/unit/test_amount_rule.py -v

# Test idempotency
pytest tests/unit/test_idempotency.py -v

# Test service layer
pytest tests/unit/test_transaction_service.py -v
```

### 5. Run Specific Test Function

```bash
pytest tests/unit/test_amount_rule.py::test_high_amount_flagged -v
```

### 6. Run Tests and Stop on First Failure

```bash
pytest tests/unit/ -v -x
```

### 7. Run Tests with Coverage Report

```bash
# Generate HTML coverage report
pytest tests/unit/ --cov=app --cov-report=html

# View report (opens in browser)
# Windows:
start htmlcov/index.html

# Mac:
open htmlcov/index.html

# Linux:
xdg-open htmlcov/index.html
```

Coverage report includes:

- Lines covered/executed
- Coverage percentage per file
- Uncovered lines highlighted

### 8. Run Tests with Detailed Output

```bash
pytest tests/unit/ -v --tb=long
```

Shows full traceback and error details.

### 9. Run Tests Matching a Pattern

```bash
# Run all velocity tests
pytest tests/unit/ -v -k velocity

# Run all tests with "flagged" in the name
pytest tests/unit/ -v -k flagged
```

---

## Test Execution in Different Environments

### Local Development (Windows/Mac/Linux)

```bash
cd fraud-detection-engine
pytest tests/unit/ -v
```

### In Docker Container

```bash
# Build container
docker build -t fraud-engine .

# Run tests inside container
docker run --rm fraud-engine pytest tests/unit/ -v
```

### With Docker Compose

```bash
# Start all services
docker compose up --build -d

# Run tests in a temporary service
docker compose run --rm api pytest tests/unit/ -v

# Clean up
docker compose down
```

---

## Understanding Test Results

### Passing Tests ✅

```
test_high_amount_flagged PASSED [  3%]
```

- Test executed successfully
- All assertions passed
- Logic works as expected

### Failing Tests ❌

```
test_high_amount_flagged FAILED [ 3%]
AssertionError: assert False == True
```

- Test condition not met
- Check error message for details
- Review test code and implementation

### Skipped Tests ⊘

```
test_future_feature SKIPPED
```

- Test marked with `@pytest.mark.skip`
- Not run but tracked

---

## Test Categories

### Amount Rule: Boundary Testing

Tests verify:

- `amount > threshold` (50,000) → flagged ✅
- `amount == threshold` → not flagged ✅
- `amount < threshold` → not flagged ✅
- Decimal amounts handled correctly ✅

### Velocity Rule: Time Windows

Tests verify:

- 4 transactions in 10-minute window → flagged ✅
- 3 transactions in window → not flagged ✅
- Transactions outside window → not counted ✅
- Time boundary conditions ✅

### Blacklist Rule: Merchant Checks

Tests verify:

- Blacklisted merchant → flagged ✅
- Non-blacklisted merchant → not flagged ✅
- Cache usage (fast lookups) → working ✅
- Null/missing merchant_id → handled gracefully ✅

### Idempotency: Duplicate Prevention

Tests verify:

- First execution → processes and marks as done ✅
- Second execution (duplicate) → skips (no duplicate alert) ✅
- Different transactions → both processed independently ✅
- Same transaction, different rules → both process ✅
- Exception in processing → not marked as processed (can retry) ✅

### Service Layer: CRUD + Integration

Tests verify:

- Transaction creation → saved to DB ✅
- Transaction publishing → sent to SNS ✅
- Transaction retrieval → loads with alerts ✅
- Transaction with decimal amounts → handled correctly ✅
- Non-existent transaction → raises 404 error ✅
- Alert retrieval → includes all fraud results ✅

### Exception Handlers: HTTP Error Codes

Tests verify:

- 404 Not Found → transaction doesn't exist ✅
- 400 Bad Request → invalid input validation ✅
- 409 Conflict → database integrity errors ✅
- 500 Internal Server Error → generic exceptions ✅
- Error messages → preserved in response ✅

---

# Future Improvements

Potential enhancements:

- Machine learning fraud scoring
- Dynamic rule configuration
- Rule versioning
- Kafka-based streaming pipeline
- Distributed tracing (OpenTelemetry)
- Multi-region deployment
- Add Dead Letter Queues for messages that fail processing

---
