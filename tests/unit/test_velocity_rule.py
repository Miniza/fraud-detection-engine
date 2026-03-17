"""
Unit tests for the Velocity Rule consumer.
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.infrastructure.models import FraudAlert, Transaction
from app.core.config import settings


@asynccontextmanager
async def mock_get_db_session(test_db):
    """Mock get_db_session context manager."""
    yield test_db


@pytest.mark.asyncio
async def test_velocity_flagged_multiple_transactions(test_db):
    """Test that rapid transactions are flagged."""
    from app.consumers.velocity_rule import handle_velocity_rule
    from unittest.mock import patch

    user_id = "user_rapid_123"
    tx_id = str(uuid.uuid4())

    # Create 4 transactions within the velocity window
    now = datetime.now(timezone.utc)
    for i in range(4):
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            amount=100.0 + i,
            currency="ZAR",
            merchant_id=f"merchant_{i}",
            status="PENDING",
            timestamp=now - timedelta(minutes=1),
        )
        test_db.add(tx)
    await test_db.commit()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.velocity_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_velocity_rule(tx_id, user_id)

    # Verify alert was created and flagged
    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert is not None
    assert alert.is_flagged is True
    assert alert.rule_name == "VELOCITY_RULE"
    assert "Velocity limit exceeded" in alert.reason
    assert result is True


@pytest.mark.asyncio
async def test_velocity_not_flagged_within_limit(test_db):
    """Test that transactions within velocity threshold are not flagged."""
    from app.consumers.velocity_rule import handle_velocity_rule
    from unittest.mock import patch

    user_id = "user_slow_123"
    tx_id = str(uuid.uuid4())

    # Create 2 transactions (below threshold of 3)
    now = datetime.now(timezone.utc)
    for i in range(2):
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            amount=100.0 + i,
            currency="ZAR",
            merchant_id=f"merchant_{i}",
            status="PENDING",
            timestamp=now - timedelta(minutes=1),
        )
        test_db.add(tx)
    await test_db.commit()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.velocity_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_velocity_rule(tx_id, user_id)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert.is_flagged is False
    assert "Within limits" in alert.reason
    assert result is True


@pytest.mark.asyncio
async def test_velocity_exactly_at_threshold(test_db):
    """Test boundary condition: exactly at velocity threshold."""
    from app.consumers.velocity_rule import handle_velocity_rule
    from unittest.mock import patch

    user_id = "user_boundary_123"
    tx_id = str(uuid.uuid4())

    # Create transactions exactly at threshold
    threshold = settings.VELOCITY_THRESHOLD
    now = datetime.now(timezone.utc)
    for i in range(threshold):
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            amount=100.0 + i,
            currency="ZAR",
            merchant_id=f"merchant_{i}",
            status="PENDING",
            timestamp=now - timedelta(minutes=1),
        )
        test_db.add(tx)
    await test_db.commit()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.velocity_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_velocity_rule(tx_id, user_id)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    # At threshold should NOT flag (only > threshold)
    assert alert.is_flagged is False


@pytest.mark.asyncio
async def test_velocity_outside_time_window(test_db):
    """Test that transactions outside velocity window are not counted."""
    from app.consumers.velocity_rule import handle_velocity_rule
    from unittest.mock import patch

    user_id = "user_old_tx_123"
    tx_id = str(uuid.uuid4())

    # Create old transaction (outside window)
    now = datetime.now(timezone.utc)
    window_mins = settings.VELOCITY_WINDOW_MINS
    old_tx = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        amount=100.0,
        currency="ZAR",
        merchant_id="merchant_old",
        status="PENDING",
        timestamp=now - timedelta(minutes=window_mins + 5),  # Outside window
    )
    test_db.add(old_tx)
    await test_db.commit()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.velocity_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_velocity_rule(tx_id, user_id)
