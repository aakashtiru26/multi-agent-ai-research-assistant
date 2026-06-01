from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.orchestration.state import JobStore
from app.services.research_service import ResearchService


def get_app_settings() -> Settings:
    return get_settings()


def get_job_store(request: Request) -> JobStore:
    return request.app.state.job_store


def get_research_service(request: Request) -> ResearchService:
    return request.app.state.research_service


async def verify_api_key(
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if not x_api_key or x_api_key != settings.api_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide X-API-Key header.",
        )
