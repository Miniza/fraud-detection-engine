from app.infrastructure.models import RulesConfig
from sqlalchemy import select
from app.infrastructure.db_session import get_db_session


async def load_rules_config():
    """Loads only enabled rules from the database"""
    async with get_db_session() as db:
        result = await db.execute(
            select(RulesConfig).where(RulesConfig.enabled.is_(True))
        )
        rules = result.scalars().all()

        return set(rule.name for rule in rules)


async def is_rule_enabled(rule_name: str) -> bool:
    results = await load_rules_config()
    return rule_name in results
