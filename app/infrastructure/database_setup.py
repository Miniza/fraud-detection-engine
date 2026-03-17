from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://admin:capitec_secret@db:5432/fraud_engine_db"
    )


settings = Settings()


class Base(DeclarativeBase):
    pass


# Module-level variables initialized lazily
engine = None
SessionLocal = None


async def initialize_db():
    """Initialize database engine and session maker."""
    global engine, SessionLocal
    if engine is None:
        engine = create_async_engine(settings.DATABASE_URL, echo=True)
        SessionLocal = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )


async def get_db():
    """Get database session."""
    if SessionLocal is None:
        await initialize_db()
    async with SessionLocal() as session:
        yield session
