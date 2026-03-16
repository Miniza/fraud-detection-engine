import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.models import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, transaction: Transaction) -> None:
        """Persists a transaction entity to the database."""
        self.session.add(transaction)
        await self.session.commit()

    async def get_by_id(self, tx_id: uuid.UUID) -> Transaction:
        """Retrieves a transaction with its pre-loaded fraud alerts."""
        result = await self.session.execute(
            select(Transaction)
            .options(selectinload(Transaction.alerts))
            .where(Transaction.id == tx_id)
        )
        return result.scalar_one_or_none()
