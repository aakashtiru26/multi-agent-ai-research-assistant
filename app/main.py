from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.middleware import RequestLoggingMiddleware
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.logging_config import setup_logging
from app.orchestration.pipeline import ResearchPipeline
from app.orchestration.state import JobStore
from app.services.research_service import ResearchService
from app.storage.postgres import PostgresStore
from app.storage.redis_cache import RedisCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    setup_logging(settings)

    job_store = JobStore()
    redis: RedisCache | None = None
    postgres: PostgresStore | None = None

    if settings.redis_enabled:
        redis = RedisCache(settings)
        await redis.connect()
        app.state.redis = redis

    if settings.postgres_enabled:
        postgres = PostgresStore(settings)
        await postgres.connect()
        app.state.postgres = postgres

    pipeline = ResearchPipeline(settings, job_store)
    research_service = ResearchService(pipeline, job_store, redis, postgres)

    app.state.job_store = job_store
    app.state.research_service = research_service

    yield

    if redis:
        await redis.disconnect()
    if postgres:
        await postgres.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Multi-agent research assistant with real-time streaming",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(api_router)

    # Try both possible frontend locations (local dev vs Docker /app)
    for candidate in [
        Path(__file__).resolve().parent.parent / "frontend",
        Path("/app/frontend"),
    ]:
        if candidate.exists():
            app.mount("/", StaticFiles(directory=str(candidate), html=True), name="frontend")
            break

    return app


app = create_app()
