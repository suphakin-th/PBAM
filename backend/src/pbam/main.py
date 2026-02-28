"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pbam.config import get_settings
from pbam.infrastructure.database.connection import dispose_engine, get_engine
from pbam.interfaces.api.v1.router import v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm up the engine
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    get_engine()  # Initialize connection pool
    yield
    # Shutdown: clean up
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Private Banking & Analytic Management API",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
