from prometheus_client import Counter, Histogram, CollectorRegistry, start_http_server
from app.core.config import settings

REGISTRY = CollectorRegistry()

# Business Metrics
TX_PROCESSED_TOTAL = Counter(
    "fraud_tx_processed_total",
    "Total transactions passing through the engine",
    ["service", "status"],
    registry=REGISTRY,
)

# Performance Metrics
RULE_LATENCY = Histogram(
    "fraud_rule_latency_seconds",
    "Time taken to evaluate a fraud rule",
    ["rule_name"],
    registry=REGISTRY,
)


def start_metrics_server():
    if settings.ENABLE_METRICS:
        # Every worker can use the same internal port (9000)
        # because they are in separate containers.
        start_http_server(settings.PROMETHEUS_METRICS_PORT)
        print(f"📊 Metrics server started on port {settings.PROMETHEUS_METRICS_PORT}")
