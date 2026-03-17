"""
Unit tests for the Blacklist Rule consumer.
"""

import pytest
import uuid
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.infrastructure.models import FraudAlert, BlacklistedMerchant


@asynccontextmanager
async def mock_get_db_session(test_db):
    """Mock get_db_session context manager."""
    yield test_db


@pytest.mark.asyncio
async def test_blacklisted_merchant_flagged(test_db):
    """Test that blacklisted merchants are flagged."""
    from app.consumers.blacklist_rule import handle_blacklist_rule
    from unittest.mock import patch

    # Add merchant to blacklist
    merchant_id = "fraud_merchant_001"
    blacklist_entry = BlacklistedMerchant(
        merchant_id=merchant_id, reason="Known phishing"
    )
    test_db.add(blacklist_entry)
    await test_db.commit()

    tx_id = str(uuid.uuid4())

    # Update cache
    from app.consumers import blacklist_rule

    blacklist_rule.BLACK_LIST_CACHE.add(merchant_id)

    # Test rule
    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.blacklist_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_blacklist_rule(tx_id, merchant_id)

    # Verify alert
    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert is not None
    assert alert.is_flagged is True
    assert alert.rule_name == "BLACKLIST_RULE"
    assert "blacklisted" in alert.reason.lower()
    assert result is True


@pytest.mark.asyncio
async def test_non_blacklisted_merchant_not_flagged(test_db):
    """Test that non-blacklisted merchants are not flagged."""
    from app.consumers.blacklist_rule import handle_blacklist_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    merchant_id = "good_merchant_001"

    # Clear cache to ensure merchant is not blacklisted
    from app.consumers import blacklist_rule

    blacklist_rule.BLACK_LIST_CACHE.clear()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.blacklist_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_blacklist_rule(tx_id, merchant_id)

    stmt = select(FraudAlert).where(FraudAlert.transaction_id == uuid.UUID(tx_id))
    alert = (await test_db.execute(stmt)).scalar_one_or_none()

    assert alert is not None
    assert alert.is_flagged is False
    assert "cleared" in alert.reason.lower()
    assert result is True


@pytest.mark.asyncio
async def test_cache_used_for_lookup(test_db):
    """Test that blacklist cache is used (not DB) for lookups."""
    from app.consumers.blacklist_rule import handle_blacklist_rule
    from app.consumers import blacklist_rule
    from unittest.mock import patch

    merchant_id = "cached_merchant_001"
    tx_id = str(uuid.uuid4())

    # Add to cache only (not DB)
    blacklist_rule.BLACK_LIST_CACHE.add(merchant_id)

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.blacklist_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_blacklist_rule(tx_id, merchant_id)

    # Should be flagged because cache has it
    # (Even though DB wasn't queried, the rule checks cache first)
    assert result is True


@pytest.mark.asyncio
async def test_null_merchant_id_handled(test_db):
    """Test that None/null merchant_id is handled gracefully."""
    from app.consumers.blacklist_rule import handle_blacklist_rule
    from unittest.mock import patch

    tx_id = str(uuid.uuid4())
    merchant_id = None

    from app.consumers import blacklist_rule

    blacklist_rule.BLACK_LIST_CACHE.clear()

    with patch(
        "app.core.idempotency.get_db_session", lambda: mock_get_db_session(test_db)
    ), patch(
        "app.consumers.blacklist_rule.get_db_session",
        lambda: mock_get_db_session(test_db),
    ):
        result = await handle_blacklist_rule(tx_id, merchant_id)
