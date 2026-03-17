import json
import asyncio
from sqlalchemy import select, func
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.models import FraudAlert, Transaction
from app.core.metrics import (
    start_metrics_server,
    RULE_LATENCY,
    TX_PROCESSED_TOTAL,
    SQS_QUEUE_DEPTH,
    WORKER_HEALTH,
    MESSAGE_PROCESSING_ERRORS,
)
from app.core.idempotency import idempotent_worker
from app.core.resilience import get_resilient_db
from circuitbreaker import CircuitBreakerError

QUEUE_NAME = "aggregator-queue"


@idempotent_worker(rule_name="AGGREGATOR")
async def handle_aggregation(
    transaction_id: str, msg_receipt: str, queue_url: str, sqs_client
):
    """
    Handles a single transaction aggregation with Circuit Breaker protection.
    """
    try:
        async with await get_resilient_db() as db:

            # Check if all required rules reported in the DB
            result = await db.execute(
                select(func.count(FraudAlert.id)).where(
                    FraudAlert.transaction_id == transaction_id
                )
            )
            alerts_count = result.scalar()

            if alerts_count < settings.EXPECTED_RULES_COUNT:
                print(
                    f"...Waiting for rules: {alerts_count}/{settings.EXPECTED_RULES_COUNT} for {transaction_id}"
                )
                return False

            flag_check = await db.execute(
                select(FraudAlert).where(
                    FraudAlert.transaction_id == transaction_id,
                    FraudAlert.is_flagged == True,
                )
            )
            any_flags = flag_check.scalars().first()
            final_status = "REJECTED" if any_flags else "APPROVED"

            await db.execute(
                Transaction.__table__.update()
                .where(Transaction.id == transaction_id)
                .values(status=final_status)
            )
            await db.commit()

            # Track metrics
            TX_PROCESSED_TOTAL.labels(
                service="aggregator", status=final_status.lower()
            ).inc()

            sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=msg_receipt)

            return True

    except CircuitBreakerError:
        MESSAGE_PROCESSING_ERRORS.labels(
            queue_name=QUEUE_NAME, error_category="circuit_breaker_open"
        ).inc()
        print(
            f"Circuit Open: Skipping DB work for {transaction_id}. DB might be under load."
        )
        return False
    except Exception as e:
        MESSAGE_PROCESSING_ERRORS.labels(
            queue_name=QUEUE_NAME, error_category="aggregation_error"
        ).inc()
        print(f"Aggregator Error: {e}")
        return False


async def run_worker():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None
    worker_name = "aggregator_worker"

    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            WORKER_HEALTH.labels(worker_name=worker_name).set(1)
        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="connection_error"
            ).inc()
            await asyncio.sleep(2)

    print(f"🚀 Aggregator listening on {QUEUE_NAME}...")

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=settings.SQS_MAX_MESSAGES,
                WaitTimeSeconds=settings.SQS_WAIT_TIMEOUT,
                AttributeNames=["ApproximateNumberOfMessages"],
            )

            # Track queue depth
            if "Attributes" in response:
                queue_depth = int(
                    response["Attributes"].get("ApproximateNumberOfMessages", 0)
                )
                SQS_QUEUE_DEPTH.labels(queue_name=QUEUE_NAME).set(queue_depth)

            # Mark worker as healthy
            WORKER_HEALTH.labels(worker_name=worker_name).set(1)

            if "Messages" not in response:
                continue

            for msg in response["Messages"]:
                with RULE_LATENCY.labels(rule_name="aggregator").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )
                        tx_id = data["transaction_id"]

                        # Call the idempotent & resilient function
                        await handle_aggregation(
                            transaction_id=tx_id,
                            msg_receipt=msg["ReceiptHandle"],
                            queue_url=queue_url,
                            sqs_client=sqs,
                        )
                    except Exception as e:
                        MESSAGE_PROCESSING_ERRORS.labels(
                            queue_name=QUEUE_NAME, error_category="parsing_error"
                        ).inc()
                        print(f"Processing Error: {e}")

        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="sqs_error"
            ).inc()
            print(f"SQS Connection Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("Stopping Aggregator...")
