from fastapi import FastAPI
from .core.config import get_settings
from .routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name, debug=settings.debug, version=settings.version
    )

    # Routers
    app.include_router(health.router)

    @app.get("/")
    async def root():
        return {"message": "Travel Expense Tracker API", "version": settings.version}

    return app


app = create_app()
