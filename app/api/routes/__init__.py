from fastapi import APIRouter, Depends

from app.api.deps import verify_api_key
from app.api.routes import health, research, websocket

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])

# Dashboard (same origin) — no API key in the browser
api_router.include_router(
    research.build_research_router(),
    prefix="/ui/research",
    tags=["ui"],
)
api_router.include_router(
    websocket.build_websocket_router(require_api_key=False),
    prefix="/ui/research",
    tags=["ui"],
)

# External / programmatic API — requires X-API-Key from server .env
api_router.include_router(
    research.build_research_router(),
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(verify_api_key)],
)
api_router.include_router(
    websocket.build_websocket_router(require_api_key=True),
    prefix="/research",
    tags=["websocket"],
)
