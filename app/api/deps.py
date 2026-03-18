from fastapi import Depends
from app.infrastructure.database_setup import get_db
from app.infrastructure.repositories.rules_repo import RulesRepository
from app.infrastructure.repositories.transaction_repo import TransactionRepository
from app.services.rules_service import RulesService
from app.services.transaction_service import TransactionService
from app.core.aws_client import get_boto_client

sns_client = get_boto_client("sns")


def get_transaction_service(db=Depends(get_db)) -> TransactionService:
    repo = TransactionRepository(db)
    return TransactionService(repo, sns_client)


def get_rule_service(db=Depends(get_db)) -> RulesService:
    repo = RulesRepository(db)
    return RulesService(repo)
