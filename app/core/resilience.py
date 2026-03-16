import logging
from circuitbreaker import circuit
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text
from app.infrastructure.database_setup import SessionLocal

logger = logging.getLogger(__name__)


class DatabaseDownError(Exception):
    pass


DB_BREAKER_CONFIG = {
    "failure_threshold": 5,
    "recovery_timeout": 60,
    "expected_exception": (OperationalError, DatabaseDownError),
}


@circuit(**DB_BREAKER_CONFIG)
async def get_resilient_db():
    """
    This function is wrapped by the circuit breaker.
    If the database is down, this function will raise a
    CircuitBreakerError without executing the code inside.
    """
    async with SessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            return session
        except (OperationalError, SQLAlchemyError) as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseDownError("Database is unreachable")
