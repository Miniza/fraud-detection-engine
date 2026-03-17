from app.infrastructure.models import RulesConfig
from app.core.idempotency import get_db_session
from sqlalchemy import select

RULES_CONFIG_CACHE = set()


async def load_rules_config():
    """Loads only enabled rules from the database into memory."""
    async with get_db_session() as db:
        result = await db.execute(
            select(RulesConfig).where(RulesConfig.enabled.is_(True))
        )
        rules = result.scalars().all()

        global RULES_CONFIG_CACHE
        RULES_CONFIG_CACHE = set(rule.name for rule in rules)

        return RULES_CONFIG_CACHE


async def is_rule_enabled(rule_name: str) -> bool:
    results = await load_rules_config()
    return rule_name in results
