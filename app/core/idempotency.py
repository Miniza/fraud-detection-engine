import functools
from sqlalchemy import select
from app.infrastructure.models import ProcessedEvent
from app.core.logger import get_logger
import uuid
from app.infrastructure.db_session import get_db_session

logger = get_logger(__name__)


def idempotent_worker(rule_name: str):
    """
    Decorator to ensure a worker only processes a specific transaction once (Indempotency).
    Auto-initializes database on first use if not already initialized.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(transaction_id: str, *args, **kwargs):
            # Look up get_db_session at call time to allow patching in tests
            get_db_session = globals()["get_db_session"]

            async with get_db_session() as db:
                tx_uuid = (
                    uuid.UUID(transaction_id)
                    if isinstance(transaction_id, str)
                    else transaction_id
                )

                # Check if already processed
                stmt = select(ProcessedEvent).where(
                    ProcessedEvent.transaction_id == tx_uuid,
                    ProcessedEvent.rule_name == rule_name,
                )
                result = await db.execute(stmt)
                if result.scalars().first():
                    logger.info(
                        f"Skipping: TX {transaction_id} already processed by {rule_name}"
                    )
                    return True  # Return true to indicate we can delete from SQS

                try:
                    success = await func(transaction_id, *args, **kwargs)

                    if success:
                        # Mark as processed
                        new_event = ProcessedEvent(
                            transaction_id=tx_uuid, rule_name=rule_name
                        )
                        db.add(new_event)
                        await db.commit()
                    return success
                except Exception as e:
                    await db.rollback()
                    raise e

        return wrapper

    return decorator
