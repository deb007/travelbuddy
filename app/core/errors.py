from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette import status
import logging

logger = logging.getLogger("app.errors")


def not_found_handler(request: Request, exc):  # type: ignore
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "not_found",
            "detail": f"No route for {request.method} {request.url.path}",
        },
    )


def validation_error_handler(request: Request, exc: RequestValidationError):  # type: ignore
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
        },
    )


def server_error_handler(request: Request, exc: Exception):  # type: ignore
    logger.exception("unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "detail": "An unexpected error occurred.",
        },
    )
