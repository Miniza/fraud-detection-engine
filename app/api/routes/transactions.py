from fastapi import APIRouter, Depends, status
import uuid
from typing import List
from app.api.schemas import TransactionCreate, TransactionAlert, TransactionResponse
from app.services.transaction_service import TransactionService
from app.api.deps import get_transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
):
    tx_id = await service.create_transaction(payload)
    return {"status": "accepted", "transaction_id": tx_id}


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction_details(
    transaction_id: uuid.UUID,
    service: TransactionService = Depends(get_transaction_service),
):
    transaction = await service.get_details(transaction_id)

    alerts = transaction.alerts or []
    is_flagged = any(alert.is_flagged for alert in alerts)

    response_alerts: List[TransactionAlert] = [
        TransactionAlert(rule=a.rule_name, reason=a.reason) for a in alerts
    ]

    return TransactionResponse(
        transaction_id=str(transaction.id),
        status=transaction.status,
        fraud_summary={
            "is_flagged": is_flagged,
            "alerts": response_alerts,
        },
    )
