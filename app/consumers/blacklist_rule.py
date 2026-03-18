import json
import asyncio
import uuid
from sqlalchemy import select
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.models import FraudAlert, BlacklistedMerchant
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
from app.core.rules_config import is_rule_enabled
from app.infrastructure.db_session import get_db_session

logger = get_logger(__name__)

QUEUE_NAME = "blacklist-queue"
BLACK_LIST_CACHE = set()
RULE_NAME = "BLACKLIST_RULE"


@idempotent_worker(rule_name=RULE_NAME)
async def handle_blacklist_rule(transaction_id: str, merchant_id: str) -> bool:
    """
    Checks if merchant is in the blacklist.
    Protected by idempotency - only executes once per transaction.
    """
    try:
        is_flagged = merchant_id in BLACK_LIST_CACHE
        reason = (
            f"Merchant {merchant_id} is blacklisted"
            if is_flagged
            else "Merchant cleared"
        )

        async with get_db_session() as db:
            alert = FraudAlert(
                transaction_id=uuid.UUID(transaction_id),
                rule_name="BLACKLIST_RULE",
                is_flagged=is_flagged,
                reason=reason,
            )
            db.add(alert)
            await db.commit()

        res_label = "flagged" if is_flagged else "cleared"
        TX_PROCESSED_TOTAL.labels(service="blacklist_rule", status=res_label).inc()

        logger.info(f"Blacklist Rule TX {transaction_id}: {res_label.upper()}")
        return True
    except Exception as e:
        MESSAGE_PROCESSING_ERRORS.labels(
            queue_name=QUEUE_NAME, error_category="processing_error"
        ).inc()
        logger.error(f"Blacklist Rule processing failed: {e}", exc_info=True)
        raise


async def refresh_blacklist_cache():
    """Syncs in-memory set with the database with exponential backoff on failure."""
    global BLACK_LIST_CACHE
    retry_delay = settings.CACHE_RETRY_DELAY
    max_retry_delay = settings.CACHE_MAX_RETRY_DELAY

    while True:
        try:
            async with get_db_session() as db:
                result = await db.execute(select(BlacklistedMerchant.merchant_id))
                new_set = set(result.scalars().all())
                BLACK_LIST_CACHE = new_set
                logger.info(
                    f"Blacklist Cache Synced: {len(BLACK_LIST_CACHE)} merchants loaded."
                )
                # Reset retry delay on success
                retry_delay = retry_delay
                await asyncio.sleep(max_retry_delay)
        except Exception as e:
            logger.error(
                f"Cache refresh failed: {e}. Retrying in {retry_delay}s...",
                exc_info=True,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)


async def process_blacklist_rule():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None
    worker_name = "blacklist_rule_worker"

    logger.info(f"Blacklist Rule Worker waiting for '{QUEUE_NAME}'...")
    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            WORKER_HEALTH.labels(worker_name=worker_name).set(1)
            logger.info(f"🚀 Blacklist Rule connected to: {queue_url}")
        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="connection_error"
            ).inc()
            await asyncio.sleep(2)

    try:
        async with get_db_session() as db:
            result = await db.execute(select(BlacklistedMerchant.merchant_id))
            global BLACK_LIST_CACHE
            BLACK_LIST_CACHE = set(result.scalars().all())
            logger.info(
                f"Initial Blacklist Cache Loaded: {len(BLACK_LIST_CACHE)} items."
            )
    except Exception as e:
        MESSAGE_PROCESSING_ERRORS.labels(
            queue_name=QUEUE_NAME, error_category="cache_load_error"
        ).inc()
        logger.warning(
            f"Initial cache load failed, starting anyway: {e}", exc_info=True
        )

    asyncio.create_task(refresh_blacklist_cache())

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
                with RULE_LATENCY.labels(rule_name="blacklist_rule").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )

                        tx_id = data["transaction_id"]
                        merchant_id = data.get("merchant_id")

                        if not await is_rule_enabled(RULE_NAME):
                            logger.warning(
                                f"Rule {RULE_NAME} is disabled. Skipping TX {tx_id}..."
                            )
                            sqs.delete_message(
                                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                            )
                            continue
                        # Call the idempotent handler
                        success = await handle_blacklist_rule(tx_id, merchant_id)

                        if success:
                            sqs.delete_message(
                                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                            )

                    except Exception as e:
                        MESSAGE_PROCESSING_ERRORS.labels(
                            queue_name=QUEUE_NAME, error_category="parsing_error"
                        ).inc()
                        logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            WORKER_HEALTH.labels(worker_name=worker_name).set(0)
            MESSAGE_PROCESSING_ERRORS.labels(
                queue_name=QUEUE_NAME, error_category="sqs_error"
            ).inc()
            logger.error(f"SQS Error: {e}", exc_info=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(process_blacklist_rule())
    except KeyboardInterrupt:
        logger.info("Stopping Blacklist Worker...")
