from fastapi import APIRouter, Depends, status
from app.services.rules_service import RulesService
from app.api.deps import get_rule_service

router = APIRouter(prefix="/rules", tags=["Rules"])


@router.get("/all")
async def get_all(
    service: RulesService = Depends(get_rule_service),
):
    rules = await service.get_all()
    return rules


@router.put("/", status_code=status.HTTP_200_OK)
async def toggle(
    rule_id: int,
    service: RulesService = Depends(get_rule_service),
):
    await service.toggle_rule(rule_id)
    return {"status": "success"}
