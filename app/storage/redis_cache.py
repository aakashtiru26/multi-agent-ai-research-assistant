import json
from uuid import UUID

from app.config import Settings
from app.logging_config import get_logger
from app.models.schemas import ResearchResponse

logger = get_logger(__name__)


class RedisCache:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("Redis connected")
        except Exception as exc:
            logger.error("Redis connection failed: %s", exc)
            self._client = None

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()

    async def health(self) -> dict:
        if not self._client:
            return {"status": "disabled", "reachable": False}
        try:
            await self._client.ping()
            return {"status": "healthy", "reachable": True}
        except Exception as exc:
            return {"status": "unhealthy", "reachable": False, "error": str(exc)}

    def _key(self, job_id: UUID) -> str:
        return f"research:job:{job_id}"

    async def cache_result(self, job_id: UUID, result: ResearchResponse) -> None:
        if not self._client:
            return
        await self._client.setex(
            self._key(job_id),
            86400,
            result.model_dump_json(),
        )

    async def get_result(self, job_id: UUID) -> ResearchResponse | None:
        if not self._client:
            return None
        raw = await self._client.get(self._key(job_id))
        if not raw:
            return None
        return ResearchResponse.model_validate(json.loads(raw))
