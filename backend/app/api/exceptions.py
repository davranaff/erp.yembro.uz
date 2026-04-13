from __future__ import annotations

from typing import Any

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.core.exceptions import AccessDeniedError, ConflictError, DomainError, NotFoundError, ValidationError


def _api_error_payload(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def _validation_error_handler(_, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_api_error_payload(
                code="validation_error",
                message=str(exc),
            ),
        )

    @app.exception_handler(NotFoundError)
    async def _not_found_error_handler(_, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_api_error_payload(
                code="not_found",
                message=str(exc),
            ),
        )

    @app.exception_handler(ConflictError)
    async def _conflict_error_handler(_, exc: ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_api_error_payload(
                code="conflict_error",
                message=str(exc),
            ),
        )

    @app.exception_handler(AccessDeniedError)
    async def _access_denied_error_handler(_, exc: AccessDeniedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_error_payload(
                code="access_denied",
                message=str(exc),
            ),
        )

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_, exc: DomainError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_api_error_payload(
                code="domain_error",
                message=str(exc),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error_handler(_, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_api_error_payload(
                code="request_validation_error",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_api_error_payload(
                code=getattr(exc, "type", "http_error") or "http_error",
                message=str(exc.detail),
                details=getattr(exc, "headers", None),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_, __: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_api_error_payload(
                code="internal_error",
                message="Unexpected server error",
            ),
        )
