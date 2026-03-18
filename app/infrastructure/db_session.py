from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_session():
    """
    Context manager that provides a database session with auto-initialization.
    If database is not initialized, initializes it on first use.
    """
    from app.infrastructure.database_setup import SessionLocal, initialize_db

    # Auto-initialize database if not already done
    if SessionLocal is None:
        await initialize_db()

    # Re-import to get the initialized SessionLocal
    from app.infrastructure.database_setup import (
        SessionLocal as InitializedSessionLocal,
    )

    async with InitializedSessionLocal() as session:
        yield session
