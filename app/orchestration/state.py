import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from app.models.schemas import ProgressEvent, ResearchResponse, ResearchStatus


class JobStore:
    """In-memory job registry with optional event subscribers."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, ResearchResponse] = {}
        self._subscribers: dict[UUID, list[asyncio.Queue[ProgressEvent | None]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._metrics = {"completed": 0, "failed": 0, "active": 0}

    async def create(self, job: ResearchResponse) -> None:
        async with self._lock:
            self._jobs[job.job_id] = job
            self._metrics["active"] += 1

    async def update(self, job: ResearchResponse) -> None:
        async with self._lock:
            self._jobs[job.job_id] = job

    async def get(self, job_id: UUID) -> ResearchResponse | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def subscribe(self, job_id: UUID) -> asyncio.Queue[ProgressEvent | None]:
        queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
        async with self._lock:
            self._subscribers[job_id].append(queue)
        return queue

    async def publish(self, event: ProgressEvent) -> None:
        async with self._lock:
            for queue in self._subscribers.get(event.job_id, []):
                await queue.put(event)

    async def close_subscribers(self, job_id: UUID) -> None:
        async with self._lock:
            for queue in self._subscribers.get(job_id, []):
                await queue.put(None)

    async def mark_finished(self, job_id: UUID, success: bool) -> None:
        async with self._lock:
            self._metrics["active"] = max(0, self._metrics["active"] - 1)
            if success:
                self._metrics["completed"] += 1
            else:
                self._metrics["failed"] += 1

    def metrics(self) -> dict[str, Any]:
        active = self._metrics["active"]
        completed = self._metrics["completed"]
        failed = self._metrics["failed"]
        return {
            "active_jobs": active,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "total_jobs": active + completed + failed,
        }
