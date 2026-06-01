from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.models.schemas import AgentStage, AgentType, ResearchResult, SummaryResult


class SummarizerAgent(BaseAgent):
    agent_type = AgentType.SUMMARIZER

    async def run(
        self,
        results: list[ResearchResult],
        job_id: UUID,
        on_event: EventCallback | None = None,
        *,
        batch: bool = True,
    ) -> list[SummaryResult]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Preserving citations in summaries",
            progress_percent=55,
        )

        if batch and len(results) > 1:
            summaries = await self._run_batch(results, job_id, on_event)
        else:
            summaries = await self._run_sequential(results, job_id, on_event)

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            f"{len(summaries)} citation-aware summaries",
            progress_percent=68,
        )
        return summaries

    async def _run_batch(
        self,
        results: list[ResearchResult],
        job_id: UUID,
        on_event: EventCallback | None,
    ) -> list[SummaryResult]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            "Consolidating verified findings",
            progress_percent=60,
        )

        blocks = "\n\n".join(
            f"ID={r.subtask_id}\nURLs: {', '.join(r.sources) or 'none'}\n{r.raw_content[:1400]}"
            for r in results
        )
        system = (
            "Research editor. For each block, write 4–6 bullets (130–170 words). "
            "KEEP all [S#] citation tags and UNVERIFIED: labels exactly as in source. "
            "Do not add new facts. JSON only: [{\"subtask_id\":\"...\",\"summary\":\"...\"}]"
        )
        raw = await self._invoke(system, f"Blocks:\n{blocks}")
        try:
            parsed = self.parse_json_block(raw)
            if isinstance(parsed, list):
                out = [
                    SummaryResult(
                        subtask_id=str(item.get("subtask_id", "")),
                        summary=str(item.get("summary", "")),
                    )
                    for item in parsed
                    if isinstance(item, dict)
                ]
                if len(out) >= len(results):
                    return out[: len(results)]
        except Exception:
            pass
        return await self._run_sequential(results, job_id, on_event)

    async def _run_sequential(
        self,
        results: list[ResearchResult],
        job_id: UUID,
        on_event: EventCallback | None,
    ) -> list[SummaryResult]:
        import asyncio

        async def _one(result: ResearchResult) -> SummaryResult:
            system = (
                "Summarize without adding facts. Preserve [S#] citations and "
                "UNVERIFIED: labels. 4–6 bullets, 130 words max."
            )
            user = f"Notes:\n{result.raw_content[:1200]}"
            text = await self._invoke(system, user)
            return SummaryResult(subtask_id=result.subtask_id, summary=text)

        return list(await asyncio.gather(*[_one(r) for r in results]))
