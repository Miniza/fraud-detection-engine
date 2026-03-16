import functools
from sqlalchemy import select
from app.infrastructure.models import ProcessedEvent
from app.infrastructure.database_setup import SessionLocal


def idempotent_worker(rule_name: str):
    """
    Decorator to ensure a worker only processes a specific transaction once (Indempotency).
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(transaction_id: str, *args, **kwargs):
            async with SessionLocal() as db:
                # Check if already processed
                stmt = select(ProcessedEvent).where(
                    ProcessedEvent.transaction_id == transaction_id,
                    ProcessedEvent.rule_name == rule_name,
                )
                result = await db.execute(stmt)
                if result.scalars().first():
                    print(
                        f"Skipping: TX {transaction_id} already processed by {rule_name}"
                    )
                    return True  # Return true to indicate we can delete from SQS

                try:
                    success = await func(transaction_id, *args, **kwargs)

                    if success:
                        # Mark as processed
                        new_event = ProcessedEvent(
                            transaction_id=transaction_id, rule_name=rule_name
                        )
                        db.add(new_event)
                        await db.commit()
                    return success
                except Exception as e:
                    await db.rollback()
                    raise e

        return wrapper

    return decorator
