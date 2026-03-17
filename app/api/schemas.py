from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional
from typing import List


class TransactionCreate(BaseModel):
    user_id: str = Field(..., example="user_12345")
    amount: Decimal = Field(..., gt=0, example=150.50)
    currency: str = Field(default="ZAR", min_length=3, max_length=3)
    merchant_id: Optional[str] = Field(None, example="merch_001")
    merchant_category: Optional[str] = Field(None, example="Retail")

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class TransactionAlert(BaseModel):
    rule: str
    reason: str


class FraudSummary(BaseModel):
    is_flagged: bool
    alerts: List[TransactionAlert]


class TransactionResponse(BaseModel):
    transaction_id: str
    status: str
    fraud_summary: FraudSummary
