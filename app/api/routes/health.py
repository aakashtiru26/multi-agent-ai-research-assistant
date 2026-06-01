from fastapi import APIRouter, Depends, Request

from app import __version__
from app.api.deps import get_app_settings
from app.config import Settings
from app.llm.ollama_client import check_ollama_health
from app.models.schemas import HealthResponse, MetricsResponse
from app.orchestration.state import JobStore

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    ollama = await check_ollama_health(settings)
    redis_status = {"status": "disabled", "reachable": False}
    postgres_status = {"status": "disabled", "reachable": False}

    if hasattr(request.app.state, "redis") and request.app.state.redis:
        redis_status = await request.app.state.redis.health()
    if hasattr(request.app.state, "postgres") and request.app.state.postgres:
        postgres_status = await request.app.state.postgres.health()

    overall = "healthy" if ollama.get("reachable") else "degraded"
    return HealthResponse(
        status=overall,
        app=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        ollama=ollama,
        redis=redis_status,
        postgres=postgres_status,
    )


@router.get("/health/ready")
async def readiness(
    settings: Settings = Depends(get_app_settings),
) -> dict:
    ollama = await check_ollama_health(settings)
    if not ollama.get("reachable"):
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"{ollama.get('backend','LLM')} not reachable")
    return {"ready": True}


@router.get("/health/live")
async def liveness() -> dict:
    return {"alive": True}


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(request: Request) -> MetricsResponse:
    store: JobStore = request.app.state.job_store
    data = store.metrics()
    return MetricsResponse(**data)
