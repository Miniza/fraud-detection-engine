"""
Unit tests for the Idempotency decorator.
"""

import pytest
import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch
from sqlalchemy import select
from app.infrastructure.models import ProcessedEvent
from app.core.idempotency import idempotent_worker


@asynccontextmanager
async def mock_get_db_session(test_db):
    """Mock get_db_session context manager."""
    yield test_db


@pytest.mark.asyncio
async def test_first_execution_succeeds(test_db):
    """Test that first execution of idempotent function succeeds and marks as processed."""
    call_count = 0

    @idempotent_worker(rule_name="TEST_RULE")
    async def test_function(transaction_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        return True

    tx_id = str(uuid.uuid4())

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await test_function(tx_id)

    assert result is True
    assert call_count == 1

    # Verify ProcessedEvent was created
    stmt = select(ProcessedEvent).where(
        ProcessedEvent.transaction_id == uuid.UUID(tx_id),
        ProcessedEvent.rule_name == "TEST_RULE",
    )
    event = (await test_db.execute(stmt)).scalar_one_or_none()
    assert event is not None


@pytest.mark.asyncio
async def test_duplicate_execution_skipped(test_db):
    """Test that duplicate execution is skipped without calling function."""
    call_count = 0

    @idempotent_worker(rule_name="TEST_RULE_2")
    async def test_function(transaction_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        return True

    tx_id = str(uuid.uuid4())

    # Pre-insert a ProcessedEvent to simulate already processed
    already_processed = ProcessedEvent(
        transaction_id=uuid.UUID(tx_id), rule_name="TEST_RULE_2"
    )
    test_db.add(already_processed)
    await test_db.commit()

    # Call function (should skip)
    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await test_function(tx_id)

    # Function should not have been called
    assert result is True
    assert call_count == 0  # Should be skipped


@pytest.mark.asyncio
async def test_multiple_transactions_independently_processed(test_db):
    """Test that different transactions are processed independently."""
    call_count = 0

    @idempotent_worker(rule_name="TEST_RULE_3")
    async def test_function(transaction_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        return True

    # Process two different transactions
    tx_id_1 = str(uuid.uuid4())
    tx_id_2 = str(uuid.uuid4())

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result1 = await test_function(tx_id_1)
        result2 = await test_function(tx_id_2)

    # Both should process
    assert result1 is True
    assert result2 is True
    assert call_count == 2

    # Both should be marked processed
    stmt = select(ProcessedEvent).where(ProcessedEvent.rule_name == "TEST_RULE_3")
    events = (await test_db.execute(stmt)).scalars().all()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_same_tx_different_rules_processed(test_db):
    """Test that same transaction is processed by different rules."""

    @idempotent_worker(rule_name="RULE_A")
    async def rule_a(transaction_id: str) -> bool:
        return True

    @idempotent_worker(rule_name="RULE_B")
    async def rule_b(transaction_id: str) -> bool:
        return True

    tx_id = str(uuid.uuid4())

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result_a = await rule_a(tx_id)
        result_b = await rule_b(tx_id)

    assert result_a is True
    assert result_b is True

    # Both rules should have processed the transaction
    stmt = select(ProcessedEvent).where(
        ProcessedEvent.transaction_id == uuid.UUID(tx_id)
    )
    events = (await test_db.execute(stmt)).scalars().all()
    assert len(events) == 2
    assert {e.rule_name for e in events} == {"RULE_A", "RULE_B"}


@pytest.mark.asyncio
async def test_exception_in_function_not_marked_processed(test_db):
    """Test that if function raises exception, it's not marked as processed."""

    @idempotent_worker(rule_name="TEST_RULE_4")
    async def failing_function(transaction_id: str) -> bool:
        raise ValueError("Test error")

    tx_id = str(uuid.uuid4())

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        with pytest.raises(ValueError):
            await failing_function(tx_id)

    # Should not be marked as processed
    stmt = select(ProcessedEvent).where(
        ProcessedEvent.transaction_id == uuid.UUID(tx_id)
    )
    event = (await test_db.execute(stmt)).scalar_one_or_none()
    assert event is None
