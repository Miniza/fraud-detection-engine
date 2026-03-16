import json
import asyncio
from sqlalchemy import select, func
from app.core.aws_client import get_boto_client
from app.core.config import settings
from app.infrastructure.models import FraudAlert, Transaction
from app.core.metrics import start_metrics_server, RULE_LATENCY, TX_PROCESSED_TOTAL
from app.core.idempotency import idempotent_worker
from app.core.resilience import get_resilient_db
from circuitbreaker import CircuitBreakerError

QUEUE_NAME = "aggregator-queue"


@idempotent_worker(rule_name="aggregator")
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
                    f"⏳ Waiting for rules: {alerts_count}/{settings.EXPECTED_RULES_COUNT} for {transaction_id}"
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
        # If the DB is down, the circuit opens. We fail fast and log it.
        print(
            f"Circuit Open: Skipping DB work for {transaction_id}. DB might be under load."
        )
        return False  # Return False so SQS retries and the ledger isn't updated
    except Exception as e:
        print(f"Aggregator Error: {e}")
        return False


# --- 2. The Worker Loop ---


async def run_worker():
    start_metrics_server()
    sqs = get_boto_client("sqs")
    queue_url = None

    while not queue_url:
        try:
            response = sqs.get_queue_url(QueueName=QUEUE_NAME)
            queue_url = response["QueueUrl"]
        except Exception:
            await asyncio.sleep(2)

    print(f"🚀 Aggregator listening on {QUEUE_NAME}...")

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

                        # Call the idempotent & resilient function
                        await handle_aggregation(
                            transaction_id=tx_id,
                            msg_receipt=msg["ReceiptHandle"],
                            queue_url=queue_url,
                            sqs_client=sqs,
                        )
                    except Exception as e:
                        print(f"❌ Processing Error: {e}")

        except Exception as e:
            print(f"❌ SQS Connection Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("Stopping Aggregator...")
