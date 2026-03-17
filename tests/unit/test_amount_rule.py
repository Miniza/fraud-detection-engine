"""
Unit tests for the Amount Rule consumer.
"""

import pytest
import uuid
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.infrastructure.models import FraudAlert
from app.core.config import settings


@asynccontextmanager
async def mock_get_db_session(test_db):
    """Mock get_db_session context manager."""
    yield test_db


@pytest.mark.asyncio
async def test_high_amount_flagged(test_db):
    """Test that transactions exceeding amount threshold are flagged."""
    from app.consumers.amount_rule import handle_amount_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    high_amount = 60000.0  # Above threshold

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.amount_rule.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await handle_amount_rule(tx_id, high_amount)

    # Verify alert was created
    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert is not None
    assert alert.is_flagged is True
    assert alert.rule_name == "HIGH_AMOUNT_RULE"
    assert "High value transaction" in alert.reason
    assert result is True


@pytest.mark.asyncio
async def test_low_amount_not_flagged(test_db):
    """Test that transactions under threshold are not flagged."""
    from app.consumers.amount_rule import handle_amount_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    low_amount = 1000.0  # Below threshold

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.amount_rule.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await handle_amount_rule(tx_id, low_amount)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert is not None
    assert alert.is_flagged is False
    assert alert.rule_name == "HIGH_AMOUNT_RULE"
    assert "Within limit" in alert.reason
    assert result is True


@pytest.mark.asyncio
async def test_amount_exactly_at_threshold(test_db):
    """Test boundary condition: amount exactly at threshold."""
    from app.consumers.amount_rule import handle_amount_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    exact_amount = float(settings.AMOUNT_THRESHOLD)  # Exactly threshold

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.amount_rule.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await handle_amount_rule(tx_id, exact_amount)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    # At threshold should NOT be flagged (only > threshold)
    assert alert.is_flagged is False


@pytest.mark.asyncio
async def test_amount_just_above_threshold(test_db):
    """Test boundary condition: amount just above threshold."""
    from app.consumers.amount_rule import handle_amount_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    above_amount = float(settings.AMOUNT_THRESHOLD) + 0.01

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.amount_rule.get_db_session", lambda: mock_get_db_session(test_db)
    ):
        result = await handle_amount_rule(tx_id, above_amount)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    # Just above should be flagged
    assert alert.is_flagged is True
