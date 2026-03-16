from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from app.infrastructure.database_setup import engine
from app.core.config import settings
from app.api.exceptions import register_exception_handlers
from app.api.routes import transactions
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.core.metrics import REGISTRY


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

register_exception_handlers(app)

app.include_router(transactions.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Endpoint for Prometheus to scrape."""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
