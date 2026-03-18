from app.infrastructure.repositories.rules_repo import RulesRepository
from app.core.logger import get_logger

logger = get_logger(__name__)


class RulesService:
    def __init__(self, repo: RulesRepository):
        self.repo = repo

    async def get_all(self):
        try:
            return await self.repo.get_all()
        except Exception as e:
            logger.error(f"Failed to retrieve rules: {e}", exc_info=True)
            raise

    async def toggle_rule(self, rule_id: int):
        try:
            await self.repo.toggle_enabled(rule_id)
            logger.info(f"Toggled rule {rule_id}")
        except ValueError as ve:
            logger.warning(f"Toggle failed: {ve}")
            raise
        except Exception as e:
            logger.error(f"Failed to toggle rule: {e}", exc_info=True)
            raise
