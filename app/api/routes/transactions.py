from fastapi import APIRouter, Depends, HTTPException, status
import uuid
from app.api.schemas import TransactionCreate
from app.services.transaction_service import TransactionService
from app.api.deps import get_transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
):
    tx_id = await service.create_transaction(payload)
    return {"status": "accepted", "transaction_id": tx_id}


@router.get("/{transaction_id}")
async def get_transaction_details(
    transaction_id: uuid.UUID,
    service: TransactionService = Depends(get_transaction_service),
):
    transaction = await service.get_details(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "transaction_id": transaction.id,
        "status": transaction.status,
        "fraud_summary": {
            "is_flagged": any(alert.is_flagged for alert in transaction.alerts),
            "alerts": [
                {"rule": a.rule_name, "reason": a.reason} for a in transaction.alerts
            ],
        },
    }
