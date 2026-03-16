import json
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.database_setup import SessionLocal
from app.infrastructure.models import Transaction, FraudAlert

# 1. Import metrics utilities
from app.core.metrics import start_metrics_server, RULE_LATENCY, TX_PROCESSED_TOTAL

# --- Constants ---
QUEUE_NAME = "velocity-queue"


async def process_velocity_rule():
    # 2. Start the metrics server for Prometheus scraping
    start_metrics_server()

    sqs = get_boto_client("sqs")
    queue_url = None

    # Resilient Queue Discovery
    print(f"🚀 Velocity Worker waiting for '{QUEUE_NAME}'...")
    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            print(f"🚀 Velocity Rule connected to: {queue_url}")
        except Exception:
            await asyncio.sleep(2)

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10
            )

            if "Messages" not in response:
                continue

            for msg in response["Messages"]:
                # 3. Track execution time (critical for DB-heavy rules)
                with RULE_LATENCY.labels(rule_name="velocity_rule").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )

                        tx_id = data["transaction_id"]
                        user_id = data["user_id"]

                        async with SessionLocal() as db:
                            # Configurable Time Window
                            lookback_limit = datetime.now(timezone.utc) - timedelta(
                                minutes=settings.VELOCITY_WINDOW_MINS
                            )

                            query = select(func.count(Transaction.id)).where(
                                Transaction.user_id == user_id,
                                Transaction.timestamp >= lookback_limit,
                            )

                            result = await db.execute(query)
                            count = result.scalar()

                            # Configurable Decision Logic
                            is_flagged = count > settings.VELOCITY_THRESHOLD
                            reason = (
                                f"Velocity limit exceeded: {count} transactions in {settings.VELOCITY_WINDOW_MINS} mins"
                                if is_flagged
                                else "Within limits"
                            )

                            # Record the Result
                            alert = FraudAlert(
                                transaction_id=tx_id,
                                rule_name="VELOCITY_RULE",
                                is_flagged=is_flagged,
                                reason=reason,
                            )
                            db.add(alert)
                            await db.commit()

                        # 4. Increment business outcome counter
                        res_label = "flagged" if is_flagged else "cleared"
                        TX_PROCESSED_TOTAL.labels(
                            service="velocity_rule", status=res_label
                        ).inc()

                        print(f"🚀 [Velocity Rule] TX {tx_id}: {res_label.upper()}")

                        # Cleanup
                        sqs.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                        )

                    except Exception as e:
                        print(f"❌ Error processing message: {e}")

        except Exception as e:
            print(f"❌ SQS Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(process_velocity_rule())
    except KeyboardInterrupt:
        print("Stopping Velocity Worker...")
