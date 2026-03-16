from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Capitec Fraud Engine"
    DATABASE_URL: str
    AWS_ENDPOINT_URL: str = "http://aws-mock:5000"
    AWS_REGION: str = "af-south-1"

    # ADD THESE: AWS Credentials
    AWS_ACCESS_KEY_ID: str = "testing"
    AWS_SECRET_ACCESS_KEY: str = "testing"

    # Infrastructure configuration
    AWS_ACCOUNT_ID: str = "123456789012"
    EXPECTED_RULES_COUNT: int = 3
    AMOUNT_THRESHOLD: float = 50000.0
    VELOCITY_WINDOW_MINS: int = 10
    VELOCITY_THRESHOLD: int = 3
    PROMETHEUS_METRICS_PORT: int = 9000
    ENABLE_METRICS: bool = True

    @property
    def TOPIC_ARN(self) -> str:
        return f"arn:aws:sns:{self.AWS_REGION}:{self.AWS_ACCOUNT_ID}:transaction-events"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
