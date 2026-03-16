from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Using the service name 'db' as defined in docker-compose
    DATABASE_URL: str = (
        "postgresql+asyncpg://admin:capitec_secret@db:5432/fraud_engine_db"
    )


settings = Settings()

# Create the async engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Create a session factory
SessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


# Dependency for FastAPI and Workers
async def get_db():
    async with SessionLocal() as session:
        yield session
