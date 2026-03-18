from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.models import RulesConfig


class RulesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> List[RulesConfig]:
        """Retrieves all rules from the database."""
        result = await self.session.execute(select(RulesConfig))
        return result.scalars().all()

    async def toggle_enabled(self, rule_id: int) -> None:
        """Toggle the enabled state of a rule."""
        result = await self.session.execute(
            select(RulesConfig).where(RulesConfig.id == rule_id)
        )
        rule = result.scalar_one_or_none()

        if not rule:
            raise ValueError(f"Rule {rule_id} not found")

        rule.enabled = not rule.enabled
        await self.session.commit()
