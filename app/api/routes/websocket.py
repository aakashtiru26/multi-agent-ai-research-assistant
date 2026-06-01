import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_job_store, get_research_service
from app.orchestration.state import JobStore
from app.services.research_service import ResearchService


def build_websocket_router(*, require_api_key: bool) -> APIRouter:
    router = APIRouter()

    @router.websocket("/{job_id}/ws")
    async def research_websocket(
        websocket: WebSocket,
        job_id: UUID,
        job_store: JobStore = Depends(get_job_store),
        service: ResearchService = Depends(get_research_service),
    ) -> None:
        if require_api_key:
            api_key = websocket.headers.get("x-api-key") or websocket.query_params.get(
                "api_key"
            )
            settings = websocket.app.state.settings
            if not api_key or api_key != settings.api_key.get_secret_value():
                await websocket.close(code=4401, reason="Unauthorized")
                return

        job = await service.get_job(job_id)
        if not job:
            await websocket.close(code=4404, reason="Job not found")
            return

        await websocket.accept()
        await websocket.send_json({"type": "connected", "job_id": str(job_id)})

        if job.report:
            await websocket.send_json(
                {"type": "complete", "report": job.report, "status": job.status.value}
            )
            await websocket.close()
            return

        queue = await job_store.subscribe(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
                    continue

                if event is None:
                    final = await service.get_job(job_id)
                    await websocket.send_json(
                        {
                            "type": "done",
                            "status": final.status.value if final else "unknown",
                            "report": final.report if final else "",
                        }
                    )
                    break

                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            await websocket.close()

    return router
