"""
Shared pytest fixtures for all tests.
Uses in-memory SQLite database, completely isolated from production.
"""

import pytest
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.infrastructure.models import (
    Transaction,
    BlacklistedMerchant,
)

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database and return a session."""
    # Import Base here to avoid PostgreSQL driver requirement at module load
    from app.infrastructure.database_setup import Base

    # Create test engine (SQLite in-memory)
    test_engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
    )

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create test session maker
    test_session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Yield session for test use
    async with test_session_maker() as session:
        yield session

    # Cleanup
    await test_engine.dispose()


@pytest.fixture
async def sample_transaction(test_db):
    """Create a sample transaction."""
    tx = Transaction(
        id=uuid.uuid4(),
        user_id="user_123",
        amount=100.0,
        currency="ZAR",
        merchant_id="merchant_001",
        merchant_category="Retail",
        status="PENDING",
    )
    test_db.add(tx)
    await test_db.commit()
    return tx


@pytest.fixture
async def sample_high_amount_transaction(test_db):
    """Create a sample high-amount transaction (for testing amount rule)."""
    tx = Transaction(
        id=uuid.uuid4(),
        user_id="user_456",
        amount=60000.0,  # Above threshold (R50,000)
        currency="ZAR",
        merchant_id="merchant_002",
        merchant_category="Electronics",
        status="PENDING",
    )
    test_db.add(tx)
    await test_db.commit()
    return tx


@pytest.fixture
async def sample_blacklisted_merchant(test_db):
    """Add a merchant to blacklist."""
    merchant = BlacklistedMerchant(
        merchant_id="bad_merchant_001", reason="Known fraudster"
    )
    test_db.add(merchant)
    await test_db.commit()
    return merchant
