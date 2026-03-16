import uuid
import json
from app.infrastructure.models import Transaction
from app.api.schemas import TransactionCreate
from app.core.config import settings
from app.infrastructure.repositories import TransactionRepository


class TransactionService:
    def __init__(self, repo: TransactionRepository, sns_client):
        self.repo = repo
        self.sns = sns_client

    async def create_transaction(self, payload: TransactionCreate) -> uuid.UUID:
        tx_id = uuid.uuid4()
        amount_float = float(payload.amount)

        new_tx = Transaction(
            id=tx_id,
            user_id=payload.user_id,
            amount=amount_float,
            status="PENDING",
        )

        await self.repo.save(new_tx)

        self.sns.publish(
            TopicArn=settings.TOPIC_ARN,
            Message=json.dumps(
                {
                    "transaction_id": str(tx_id),
                    "user_id": payload.user_id,
                    "amount": amount_float,
                    "merchant_id": payload.merchant_id,
                    "merchant_category": payload.merchant_category,
                }
            ),
        )
        return tx_id

    async def get_details(self, transaction_id: uuid.UUID):
        return await self.repo.get_by_id(transaction_id)
