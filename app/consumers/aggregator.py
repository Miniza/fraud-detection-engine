import json
import asyncio
from sqlalchemy import select, func
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.database_setup import SessionLocal
from app.infrastructure.models import FraudAlert, Transaction
from app.core.metrics import start_metrics_server, RULE_LATENCY, TX_PROCESSED_TOTAL

QUEUE_NAME = "aggregator-queue"


async def process_aggregator():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None

    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
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
                with RULE_LATENCY.labels(rule_name="aggregator").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )
                        tx_id = data["transaction_id"]

                        async with SessionLocal() as db:
                            result = await db.execute(
                                select(func.count(FraudAlert.id)).where(
                                    FraudAlert.transaction_id == tx_id
                                )
                            )
                            alerts_count = result.scalar()

                            if alerts_count >= settings.EXPECTED_RULES_COUNT:
                                flag_check = await db.execute(
                                    select(FraudAlert).where(
                                        FraudAlert.transaction_id == tx_id,
                                        FraudAlert.is_flagged == True,
                                    )
                                )
                                any_flags = flag_check.scalars().first()

                                final_status = "REJECTED" if any_flags else "APPROVED"

                                await db.execute(
                                    Transaction.__table__.update()
                                    .where(Transaction.id == tx_id)
                                    .values(status=final_status)
                                )
                                await db.commit()

                                # 4. Track Final Business Outcomes
                                # This allows you to see the Real-Time Approval Rate
                                TX_PROCESSED_TOTAL.labels(
                                    service="aggregator", status=final_status.lower()
                                ).inc()

                                sqs.delete_message(
                                    QueueUrl=queue_url,
                                    ReceiptHandle=msg["ReceiptHandle"],
                                )
                    except Exception as e:
                        print(f"❌ Aggregator Error: {e}")

        except Exception as e:
            print(f"❌ SQS Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(process_aggregator())
    except KeyboardInterrupt:
        print("Stopping Aggregator...")
