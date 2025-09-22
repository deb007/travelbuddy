from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .core.config import get_settings
from .core.logging import init_logging, request_context_middleware
from .core import errors
from .routers import health, budgets


def create_app() -> FastAPI:
    settings = get_settings()
    # Initialize logging early
    init_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name, debug=settings.debug, version=settings.version
    )

    # Middleware (request id / structured logging)
    app.middleware("http")(request_context_middleware)

    # Error handlers
    app.add_exception_handler(StarletteHTTPException, errors.not_found_handler)
    app.add_exception_handler(RequestValidationError, errors.validation_error_handler)
    app.add_exception_handler(Exception, errors.server_error_handler)

    # Routers
    app.include_router(health.router)
    app.include_router(budgets.router)

    @app.get("/")
    async def root():
        return {"message": "Travel Expense Tracker API", "version": settings.version}

    return app


app = create_app()
