from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .core.config import get_settings, Settings
from .core.logging import init_logging, request_context_middleware
from .db.migrate import apply_migrations
from .core import errors
from .routers import health, budgets, expenses, timeline, forex, rates, analytics


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """Application factory.

    settings_override: pass an already constructed Settings instance for tests
    to isolate environment (e.g., temp DB). Falls back to cached get_settings().
    """
    settings = settings_override or get_settings()
    # Initialize logging early
    init_logging(debug=settings.debug)

    # Ensure database schema (idempotent) so test-injected fresh DBs have tables
    try:
        apply_migrations(settings.db_path)  # type: ignore[arg-type]
    except Exception:
        # Failing to init DB is fatal; re-raise after logging
        import logging

        logging.getLogger("app").exception("failed to apply migrations on startup")
        raise

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
    app.include_router(expenses.router)
    app.include_router(timeline.router)
    app.include_router(forex.router)
    app.include_router(rates.router)
    app.include_router(analytics.router)

    @app.get("/")
    async def root():
        return {"message": "Travel Expense Tracker API", "version": settings.version}

    return app


app = create_app()
