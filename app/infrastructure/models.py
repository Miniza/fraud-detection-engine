from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database_setup import Base
import uuid


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transaction_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    rule_name = Column(String, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("transaction_id", "rule_name", name="uq_tx_rule"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="ZAR")
    merchant_id = Column(String)
    merchant_category = Column(String)
    status = Column(String, default="PENDING")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    alerts = relationship("FraudAlert", back_populates="transaction", lazy="selectin")


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_name = Column(String, nullable=False)
    is_flagged = Column(Boolean, default=False)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transaction = relationship("Transaction", back_populates="alerts")


class BlacklistedMerchant(Base):
    __tablename__ = "blacklisted_merchants"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, unique=True, nullable=False, index=True)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RulesConfig(Base):
    __tablename__ = "fraud_rules_config"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
