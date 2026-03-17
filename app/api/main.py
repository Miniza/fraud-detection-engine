from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from app.infrastructure.database_setup import initialize_db, engine
from app.core.config import settings
from app.api.exception_handlers import register_exception_handlers
from app.api.routes import transactions
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.core.metrics import REGISTRY, API_REQUEST_LATENCY
from app.core.logger import get_logger
import time

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await initialize_db()
    yield
    # Dispose engine on shutdown
    if engine is not None:
        await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    description="This a Distributed System That Does Financial Fraud Checks Against a Transaction. 🚀",
    version="1.0.0",
    contact={
        "name": "Minenhle Dlamini",
        "url": "https://www.linkedin.com/in/minenhle-dlamini-803588197",
        "email": "minenhledlamini37@gmail.com",
    },
)

register_exception_handlers(app)

app.include_router(transactions.router)


@app.middleware("http")
async def add_metrics_middleware(request: Request, call_next):
    """Record API endpoint latency metrics."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Extract endpoint path (remove path parameters for consistent metric labels)
    endpoint = request.url.path
    method = request.method
    status_code = response.status_code

    API_REQUEST_LATENCY.labels(
        method=method, endpoint=endpoint, status_code=status_code
    ).observe(process_time)

    return response


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Endpoint for Prometheus to scrape."""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
