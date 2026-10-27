import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | list | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Account not found"},
    409: {"model": ErrorResponse, "description": "Duplicate reference or balance conflict"},
    422: {"model": ErrorResponse, "description": "Invalid request data"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
    503: {"model": ErrorResponse, "description": "Database operation failed"},
}


class LedgerError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details


def error_response(status: int, code: str, message: str, details=None):
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder({"error": {"code": code, "message": message, "details": details}}),
    )


def register_error_handlers(app: FastAPI):
    @app.exception_handler(LedgerError)
    async def ledger_error(request: Request, exc: LedgerError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return error_response(422, "validation_error", "Invalid request data", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed", exc_info=exc)
        return error_response(503, "database_error", "Database operation failed; retry later")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unexpected application error", exc_info=exc)
        return error_response(500, "internal_error", "An unexpected error occurred")
