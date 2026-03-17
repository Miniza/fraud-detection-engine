# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from .rules_config import RULES_CONFIG_CACHE


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    # Project & database
    PROJECT_NAME: str = "Capitec Fraud Engine"
    DATABASE_URL: str = (
        "postgresql+asyncpg://admin:capitec_secret@db:5432/fraud_engine_db"
    )

    # AWS mock setup
    AWS_ENDPOINT_URL: str = "http://aws-mock:5000"
    AWS_REGION: str = "af-south-1"
    AWS_ACCESS_KEY_ID: str = "testing"
    AWS_SECRET_ACCESS_KEY: str = "testing"
    AWS_ACCOUNT_ID: str = "123456789012"

    # Fraud rules configuration
    AMOUNT_THRESHOLD: float = 50000.0
    VELOCITY_WINDOW_MINS: int = 10
    VELOCITY_THRESHOLD: int = 3

    # Metrics & observability
    PROMETHEUS_METRICS_PORT: int = 9000
    ENABLE_METRICS: bool = True

    # SQS configuration
    SQS_WAIT_TIMEOUT: int = 20
    SQS_MAX_MESSAGES: int = 10

    # Rules cache retry/delay
    CACHE_RETRY_DELAY: int = 5
    CACHE_MAX_RETRY_DELAY: int = 300

    @property
    def TOPIC_ARN(self) -> str:
        """Construct SNS topic ARN dynamically."""
        return f"arn:aws:sns:{self.AWS_REGION}:{self.AWS_ACCOUNT_ID}:transaction-events"

    @property
    def EXPECTED_RULES_COUNT(self) -> int:
        """Return the current number of enabled rules in memory."""
        return len(RULES_CONFIG_CACHE)


settings = Settings()
