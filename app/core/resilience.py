import logging
from contextlib import asynccontextmanager
from circuitbreaker import circuit
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DatabaseDownError(Exception):
    pass


DB_BREAKER_CONFIG = {
    "failure_threshold": 5,
    "recovery_timeout": 60,
    "expected_exception": (OperationalError, DatabaseDownError),
}


@asynccontextmanager
async def get_resilient_db():
    """
    Context manager with circuit breaker protection.
    Auto-initializes database if not already initialized.
    If the database is down, the circuit breaker will raise CircuitBreakerError.
    """
    from app.infrastructure.database_setup import SessionLocal, initialize_db

    # Auto-initialize database if not already done
    if SessionLocal is None:
        await initialize_db()

    # Re-import to get the initialized SessionLocal
    from app.infrastructure.database_setup import (
        SessionLocal as InitializedSessionLocal,
    )

    async with InitializedSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            yield session
        except (OperationalError, SQLAlchemyError) as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseDownError("Database is unreachable")
