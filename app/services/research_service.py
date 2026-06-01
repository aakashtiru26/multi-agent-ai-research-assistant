import asyncio
from uuid import UUID

from app.logging_config import get_logger
from app.models.schemas import ResearchRequest, ResearchResponse, ResearchStatus, new_job_id
from app.orchestration.pipeline import ResearchPipeline
from app.orchestration.state import JobStore
from app.storage.postgres import PostgresStore
from app.storage.redis_cache import RedisCache

logger = get_logger(__name__)


class ResearchService:
    def __init__(
        self,
        pipeline: ResearchPipeline,
        job_store: JobStore,
        redis: RedisCache | None = None,
        postgres: PostgresStore | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._job_store = job_store
        self._redis = redis
        self._postgres = postgres
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def start_research(self, request: ResearchRequest) -> ResearchResponse:
        job_id = new_job_id()
        job = ResearchResponse(
            job_id=job_id,
            status=ResearchStatus.PENDING,
            query=request.query,
        )
        await self._job_store.create(job)

        if self._postgres:
            await self._postgres.save_job(job)

        task = asyncio.create_task(self._run_job(job_id, request))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return job

    async def _run_job(self, job_id: UUID, request: ResearchRequest) -> None:
        try:
            result = await self._pipeline.execute(job_id, request)
            if self._redis:
                await self._redis.cache_result(job_id, result)
            if self._postgres:
                await self._postgres.save_job(result)
        except Exception:
            logger.exception("Background job %s failed", job_id)

    async def get_job(self, job_id: UUID) -> ResearchResponse | None:
        job = await self._job_store.get(job_id)
        if job:
            return job
        if self._redis:
            return await self._redis.get_result(job_id)
        if self._postgres:
            return await self._postgres.get_job(job_id)
        return None
