import json
import asyncio
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.database_setup import SessionLocal
from app.infrastructure.models import FraudAlert
from app.core.metrics import start_metrics_server, RULE_LATENCY, TX_PROCESSED_TOTAL

QUEUE_NAME = "amount-queue"


async def process_amount_rule():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None

    print(f"💰 Amount Rule Worker waiting for '{QUEUE_NAME}'...")
    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
            print(f"🚀 Amount Rule connected to: {queue_url}")
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
                with RULE_LATENCY.labels(rule_name="amount_rule").time():
                    try:
                        body = json.loads(msg["Body"])
                        data = (
                            json.loads(body["Message"]) if "Message" in body else body
                        )

                        tx_id = data["transaction_id"]
                        amount = float(data["amount"])

                        is_flagged = amount > settings.AMOUNT_THRESHOLD
                        reason = (
                            f"High value transaction: exceeds R{settings.AMOUNT_THRESHOLD:,.2f}"
                            if is_flagged
                            else "Within limit"
                        )

                        async with SessionLocal() as db:
                            alert = FraudAlert(
                                transaction_id=tx_id,
                                rule_name="HIGH_AMOUNT_RULE",
                                is_flagged=is_flagged,
                                reason=reason,
                            )
                            db.add(alert)
                            await db.commit()

                        res_label = "flagged" if is_flagged else "cleared"
                        TX_PROCESSED_TOTAL.labels(
                            service="amount_rule", status=res_label
                        ).inc()

                        print(f"💰 [Amount Rule] TX {tx_id}: {res_label.upper()}")

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
        asyncio.run(process_amount_rule())
    except KeyboardInterrupt:
        print("Stopping Amount Rule Worker...")
