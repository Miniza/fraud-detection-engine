import uuid
import json
from app.infrastructure.models import Transaction
from app.api.schemas import TransactionCreate
from app.core.config import settings
from app.infrastructure.repositories import TransactionRepository
from app.api.exceptions import TransactionNotFoundError
from app.core.logger import get_logger

logger = get_logger(__name__)


class TransactionService:
    def __init__(self, repo: TransactionRepository, sns_client):
        self.repo = repo
        self.sns = sns_client

    async def create_transaction(self, payload: TransactionCreate) -> uuid.UUID:
        try:
            tx_id = uuid.uuid4()
            amount_float = float(payload.amount)

            new_tx = Transaction(
                id=tx_id,
                user_id=payload.user_id,
                amount=amount_float,
                status="PENDING",
                merchant_id=payload.merchant_id,
                merchant_category=payload.merchant_category,
            )

            # Might Lead to dual write issues, with proper resources will have to use outbox transactional pattern to ensure consistency between DB and SNS
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
            logger.info(f"Transaction created: {tx_id}")
            return tx_id
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}", exc_info=True)
            raise

    async def get_details(self, transaction_id: uuid.UUID):
        transaction = await self.repo.get_by_id(transaction_id)
        if not transaction:
            logger.warning(f"Transaction not found: {transaction_id}")
            raise TransactionNotFoundError(str(transaction_id))
        return transaction
