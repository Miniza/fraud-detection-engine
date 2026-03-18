"""
Unit tests for TransactionService.
"""

import pytest
import uuid
from sqlalchemy import select
from app.infrastructure.models import Transaction
from app.infrastructure.repositories.transaction_repo import TransactionRepository
from app.services.transaction_service import TransactionService
from app.api.exception_handlers import TransactionNotFoundError
from app.api.schemas import TransactionCreate
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_create_transaction_success(test_db):
    """Test successful transaction creation."""

    # Create mock SNS client
    mock_sns = MagicMock()
    mock_sns.publish = MagicMock(return_value={"MessageId": "123"})

    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    payload = TransactionCreate(
        user_id="user_123",
        amount="1000.50",
        merchant_id="merch_001",
        merchant_category="Retail",
    )

    tx_id = await service.create_transaction(payload)

    # Verify transaction was saved
    stmt = select(Transaction).where(Transaction.id == tx_id)
    saved_tx = (await test_db.execute(stmt)).scalar_one_or_none()

    assert saved_tx is not None
    assert saved_tx.user_id == "user_123"
    assert saved_tx.amount == 1000.50
    assert saved_tx.status == "PENDING"

    # Verify SNS was called
    assert mock_sns.publish.called


@pytest.mark.asyncio
async def test_create_transaction_publishes_to_sns(test_db):
    """Test that transaction creation publishes to SNS."""

    mock_sns = MagicMock()
    mock_sns.publish = MagicMock(return_value={"MessageId": "456"})

    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    payload = TransactionCreate(
        user_id="user_456",
        amount="5000.00",
        merchant_id="merch_002",
        merchant_category="Electronics",
    )

    await service.create_transaction(payload)

    # Verify SNS.publish was called with correct data
    assert mock_sns.publish.called
    call_args = mock_sns.publish.call_args

    # Check that TopicArn was passed
    assert "TopicArn" in call_args[1]
    assert "Message" in call_args[1]

    # Check message contains transaction data
    import json

    message = json.loads(call_args[1]["Message"])
    assert message["user_id"] == "user_456"
    assert float(message["amount"]) == 5000.0
    assert message["merchant_id"] == "merch_002"


@pytest.mark.asyncio
async def test_get_transaction_success(test_db):
    """Test successful transaction retrieval."""

    # Create a transaction
    tx = Transaction(
        id=uuid.uuid4(),
        user_id="user_789",
        amount=2000.0,
        currency="ZAR",
        merchant_id="merch_003",
        status="PENDING",
    )
    test_db.add(tx)
    await test_db.commit()

    # Retrieve it
    mock_sns = MagicMock()
    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    retrieved = await service.get_details(tx.id)

    assert retrieved is not None
    assert retrieved.id == tx.id
    assert retrieved.user_id == "user_789"
    assert retrieved.amount == 2000.0


@pytest.mark.asyncio
async def test_get_transaction_with_alerts(test_db):
    """Test that transaction retrieval includes alerts."""
    from app.infrastructure.models import FraudAlert

    # Create transaction with alert
    tx = Transaction(
        id=uuid.uuid4(),
        user_id="user_alert",
        amount=3000.0,
        currency="ZAR",
        merchant_id="merch_004",
        status="PENDING",
    )
    test_db.add(tx)
    await test_db.commit()

    alert = FraudAlert(
        transaction_id=tx.id,
        rule_name="AMOUNT_RULE",
        is_flagged=True,
        reason="High amount",
    )
    test_db.add(alert)
    await test_db.commit()

    # Retrieve
    mock_sns = MagicMock()
    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    retrieved = await service.get_details(tx.id)

    assert retrieved is not None
    assert len(retrieved.alerts) == 1
    assert retrieved.alerts[0].rule_name == "AMOUNT_RULE"


@pytest.mark.asyncio
async def test_get_nonexistent_transaction_raises_error(test_db):
    """Test that retrieving non-existent transaction raises TransactionNotFoundError."""

    mock_sns = MagicMock()
    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    nonexistent_id = uuid.uuid4()

    with pytest.raises(TransactionNotFoundError):
        await service.get_details(nonexistent_id)


@pytest.mark.asyncio
async def test_create_transaction_with_decimal_amount(test_db):
    """Test that transaction creation handles decimal amounts correctly."""

    mock_sns = MagicMock()
    repo = TransactionRepository(test_db)
    service = TransactionService(repo, mock_sns)

    payload = TransactionCreate(
        user_id="user_decimal",
        amount="999.99",
        merchant_id="merch_005",
        merchant_category="Retail",
    )

    tx_id = await service.create_transaction(payload)

    stmt = select(Transaction).where(Transaction.id == tx_id)
    saved_tx = (await test_db.execute(stmt)).scalar_one_or_none()

    assert saved_tx.amount == 999.99
