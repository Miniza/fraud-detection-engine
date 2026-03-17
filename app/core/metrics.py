from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    start_http_server,
)
from app.core.config import settings

REGISTRY = CollectorRegistry()

# ===== Business Metrics =====
TX_PROCESSED_TOTAL = Counter(
    "fraud_tx_processed_total",
    "Total transactions passing through the engine",
    ["service", "status"],
    registry=REGISTRY,
)

# ===== Performance Metrics =====
RULE_LATENCY = Histogram(
    "fraud_rule_latency_seconds",
    "Time taken to evaluate a fraud rule",
    ["rule_name"],
    registry=REGISTRY,
)

API_REQUEST_LATENCY = Histogram(
    "fraud_api_request_latency_seconds",
    "Time taken to process an API request",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
    registry=REGISTRY,
)

# ===== Infrastructure Metrics =====
SQS_QUEUE_DEPTH = Gauge(
    "fraud_sqs_queue_depth",
    "Current depth of SQS queue (number of messages waiting)",
    ["queue_name"],
    registry=REGISTRY,
)

WORKER_HEALTH = Gauge(
    "fraud_worker_health",
    "Worker health status (1=healthy, 0=unhealthy)",
    ["worker_name"],
    registry=REGISTRY,
)

DB_POOL_CONNECTIONS = Gauge(
    "fraud_db_pool_connections",
    "Number of active database connections in the pool",
    ["pool_name"],
    registry=REGISTRY,
)

# ===== Error Metrics =====
ERROR_RATE = Counter(
    "fraud_errors_total",
    "Total number of errors by type and service",
    ["service", "error_type"],
    registry=REGISTRY,
)

MESSAGE_PROCESSING_ERRORS = Counter(
    "fraud_message_processing_errors_total",
    "Total message processing errors by queue",
    ["queue_name", "error_category"],
    registry=REGISTRY,
)


def start_metrics_server():
    if settings.ENABLE_METRICS:
        start_http_server(settings.PROMETHEUS_METRICS_PORT)
        print(f"...Metrics server started on port {settings.PROMETHEUS_METRICS_PORT}")
