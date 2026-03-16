# Real-Time Fraud Detection Engine

A **high-concurrency, event-driven fraud detection system** built with **FastAPI**, **PostgreSQL**, and **AWS SNS/SQS**.

This project demonstrates a **production-style fan-out architecture** where financial transactions are processed through multiple independent fraud detection rules **in parallel**.

The system simulates how modern financial platforms evaluate transactions using **distributed workers and asynchronous processing**.

---

# Architecture Overview

The system uses a **fan-out messaging pattern** to evaluate transactions across multiple fraud detection rules simultaneously.

## Processing Flow

1. **API Gateway (Producer)**
   - A FastAPI service receives transaction requests.
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
git clone https://github.com/Miniza/fraud-detection-engine.git
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
  "merchant_id": "merch_999",
  "merchant_category": "Retail"
}
```

### Response

```json
{
  "status": "accepted",
  "transaction_id": "2607b08f-c862-43fe-b637-01c90da78ad6"
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
  "transaction_id": "2607b08f-c862-43fe-b637-01c90da78ad6",
  "status": "REJECTED",
  "fraud_summary": {
    "is_flagged": true,
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
        "reason": "Merchant merch_999 is blacklisted"
      }
    ]
  }
}
```

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

### Prometheus

```
http://localhost:9090
```

### Grafana

```
http://localhost:3000
```

---

# Future Improvements

Potential enhancements:

- Machine learning fraud scoring
- Dynamic rule configuration
- Rule versioning
- Kafka-based streaming pipeline
- Distributed tracing (OpenTelemetry)
- Multi-region deployment

---
