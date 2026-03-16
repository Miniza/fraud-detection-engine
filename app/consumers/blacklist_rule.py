import json
import asyncio
import uuid
from sqlalchemy import select
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.database_setup import SessionLocal
from app.infrastructure.models import FraudAlert, BlacklistedMerchant
from app.core.metrics import start_metrics_server, RULE_LATENCY, TX_PROCESSED_TOTAL

QUEUE_NAME = "blacklist-queue"
BLACK_LIST_CACHE = set()


async def refresh_blacklist_cache():
    """Syncs in-memory set with the database every 5 minutes."""
    global BLACK_LIST_CACHE
    while True:
        try:
            async with SessionLocal() as db:
                result = await db.execute(select(BlacklistedMerchant.merchant_id))
                new_set = set(result.scalars().all())
                BLACK_LIST_CACHE = new_set
                print(
                    f"Blacklist Cache Synced: {len(BLACK_LIST_CACHE)} merchants loaded."
                )
        except Exception as e:
            print(f"Cache refresh failed: {e}")

        await asyncio.sleep(300)


async def process_blacklist_rule():
    start_metrics_server()

    sqs = get_boto_client("sqs")
    queue_url = None

    print(f"Blacklist Rule Worker waiting for '{QUEUE_NAME}'...")
    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            print(f"🚀 Blacklist Rule connected to: {queue_url}")
        except Exception:
            await asyncio.sleep(2)

    try:
        async with SessionLocal() as db:
            result = await db.execute(select(BlacklistedMerchant.merchant_id))
            global BLACK_LIST_CACHE
            BLACK_LIST_CACHE = set(result.scalars().all())
            print(f"Initial Blacklist Cache Loaded: {len(BLACK_LIST_CACHE)} items.")
    except Exception as e:
        print(f"Initial cache load failed, starting anyway: {e}")

    asyncio.create_task(refresh_blacklist_cache())

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10
            )

            if "Messages" not in response:
                continue

            for msg in response["Messages"]:
                with RULE_LATENCY.labels(rule_name="blacklist_rule").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )

                        tx_id = uuid.UUID(data["transaction_id"])
                        merchant_id = data.get("merchant_id")

                        is_flagged = merchant_id in BLACK_LIST_CACHE
                        reason = (
                            f"Merchant {merchant_id} is blacklisted"
                            if is_flagged
                            else "Merchant cleared"
                        )

                        async with SessionLocal() as db:
                            alert = FraudAlert(
                                transaction_id=tx_id,
                                rule_name="BLACKLIST_RULE",
                                is_flagged=is_flagged,
                                reason=reason,
                            )
                            db.add(alert)
                            await db.commit()

                        # 5. Increment Business Metric
                        res_label = "flagged" if is_flagged else "cleared"
                        TX_PROCESSED_TOTAL.labels(
                            service="blacklist_rule", status=res_label
                        ).inc()

                        print(f"[Blacklist Rule] TX {tx_id}: {res_label.upper()}")

                        sqs.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                        )

                    except Exception as e:
                        print(f"Error processing message: {e}")

        except Exception as e:
            print(f"SQS Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(process_blacklist_rule())
    except KeyboardInterrupt:
        print("Stopping Blacklist Worker...")
