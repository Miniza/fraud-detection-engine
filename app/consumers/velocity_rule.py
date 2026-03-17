import json
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.database_setup import SessionLocal
from app.infrastructure.models import Transaction, FraudAlert
from app.core.metrics import (
    start_metrics_server,
    RULE_LATENCY,
    TX_PROCESSED_TOTAL,
    SQS_QUEUE_DEPTH,
    WORKER_HEALTH,
    MESSAGE_PROCESSING_ERRORS,
)
from app.core.idempotency import idempotent_worker
from app.core.logger import get_logger

logger = get_logger(__name__)

QUEUE_NAME = "velocity-queue"


@idempotent_worker(rule_name="VELOCITY_RULE")
async def handle_velocity_rule(transaction_id: str, user_id: str) -> bool:
    """
    Detects rapid transaction patterns within a time window.
    Protected by idempotency - only executes once per transaction.
    """
    try:
        async with SessionLocal() as db:
            lookback_limit = datetime.now(timezone.utc) - timedelta(
                minutes=settings.VELOCITY_WINDOW_MINS
            )

            query = select(func.count(Transaction.id)).where(
                Transaction.user_id == user_id,
                Transaction.timestamp >= lookback_limit,
            )

            result = await db.execute(query)
            count = result.scalar()
            is_flagged = count > settings.VELOCITY_THRESHOLD
            reason = (
                f"Velocity limit exceeded: {count} transactions in {settings.VELOCITY_WINDOW_MINS} mins"
                if is_flagged
                else "Within limits"
            )

            alert = FraudAlert(
                transaction_id=transaction_id,
                rule_name="VELOCITY_RULE",
                is_flagged=is_flagged,
                reason=reason,
            )
            db.add(alert)
            await db.commit()

        res_label = "flagged" if is_flagged else "cleared"
        TX_PROCESSED_TOTAL.labels(service="velocity_rule", status=res_label).inc()

        logger.info(f"Velocity Rule TX {transaction_id}: {res_label.upper()}")
        return True
    except Exception as e:
        MESSAGE_PROCESSING_ERRORS.labels(
            queue_name=QUEUE_NAME, error_category="processing_error"
        ).inc()
        logger.error(f"Velocity Rule processing failed: {e}", exc_info=True)
        raise


async def process_velocity_rule():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None
    worker_name = "velocity_rule_worker"

    logger.info(f"Velocity Worker waiting for '{QUEUE_NAME}'...")
    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            WORKER_HEALTH.labels(worker_name=worker_name).set(1)
            logger.info(f"🚀 Velocity Rule connected to: {queue_url}")
        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="connection_error"
            ).inc()
            await asyncio.sleep(2)

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
                with RULE_LATENCY.labels(rule_name="velocity_rule").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )

                        tx_id = data["transaction_id"]
                        user_id = data["user_id"]

                        # Call the idempotent handler
                        success = await handle_velocity_rule(tx_id, user_id)

                        if success:
                            sqs.delete_message(
                                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                            )

                    except Exception as e:
                        MESSAGE_PROCESSING_ERRORS.labels(
                            queue_name=QUEUE_NAME, error_category="parsing_error"
                        ).inc()
                        print(f"Error processing message: {e}")

        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="sqs_error"
            ).inc()
            print(f"SQS Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(process_velocity_rule())
    except KeyboardInterrupt:
        print("Stopping Velocity Worker...")
