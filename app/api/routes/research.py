import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_job_store, get_research_service
from app.models.schemas import (
    AgentStage,
    AgentType,
    ProgressEvent,
    ResearchRequest,
    ResearchResponse,
)
from app.orchestration.state import JobStore
from app.services.research_service import ResearchService


def build_research_router() -> APIRouter:
    """Research endpoints (mount with or without API-key dependency)."""
    router = APIRouter()

    @router.post("", response_model=ResearchResponse, status_code=202)
    async def create_research(
        body: ResearchRequest,
        service: ResearchService = Depends(get_research_service),
    ) -> ResearchResponse:
        return await service.start_research(body)

    @router.get("/{job_id}", response_model=ResearchResponse)
    async def get_research(
        job_id: UUID,
        service: ResearchService = Depends(get_research_service),
    ) -> ResearchResponse:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @router.get("/{job_id}/stream")
    async def stream_research_sse(
        job_id: UUID,
        job_store: JobStore = Depends(get_job_store),
        service: ResearchService = Depends(get_research_service),
    ) -> StreamingResponse:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        async def event_generator():
            queue = await job_store.subscribe(job_id)
            yield f"data: {json.dumps({'type': 'connected', 'job_id': str(job_id)})}\n\n"

            if job.report:
                done = ProgressEvent(
                    job_id=job_id,
                    agent=AgentType.REPORTER,
                    stage=AgentStage.COMPLETED,
                    message="Job already completed",
                    progress_percent=100,
                )
                yield done.to_sse()
                yield "data: {\"type\": \"done\"}\n\n"
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    final = await service.get_job(job_id)
                    if final and final.report:
                        yield f"data: {json.dumps({'type': 'report', 'report': final.report})}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    break

                yield event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
