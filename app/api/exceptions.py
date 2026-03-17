from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from app.core.logger import get_logger

logger = get_logger(__name__)


class TransactionNotFoundError(Exception):
    """Raised when a transaction cannot be found by ID."""

    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        super().__init__(f"Transaction {transaction_id} not found")


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(TransactionNotFoundError)
    async def transaction_not_found_handler(
        request: Request, exc: TransactionNotFoundError
    ):
        """Handle transaction lookup failures."""
        logger.warning(
            f"Transaction not found: {exc.transaction_id} on {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "NOT_FOUND",
                "message": f"Transaction {exc.transaction_id} not found.",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Handle malformed JSON or invalid types (400 instead of 422)."""
        logger.warning(
            f"Request validation error on {request.method} {request.url.path}: {exc.errors()}"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "INVALID_INPUT",
                "message": "The request payload is invalid.",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        """Handle database unique constraint violations (e.g. duplicate TX IDs)."""
        logger.warning(
            f"Database integrity error on {request.method} {request.url.path}: {exc}"
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "DUPLICATE_RESOURCE",
                "message": "A transaction with this ID already exists.",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """The 'Safety Net' to catch 500s and hide the stack trace."""
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}", exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )
