import asyncio
from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.logging_config import get_logger
from app.models.research_context import ResearchBrief
from app.models.schemas import AgentStage, AgentType, ResearchResult, Subtask, SummaryResult
from app.services.retrieval import format_evidence_block, gather_evidence

logger = get_logger(__name__)


def _grounded_system(brief: ResearchBrief | None) -> str:
    base = (
        "You are an expert ML/NLP research analyst (GPT-Researcher / Perplexity quality).\n\n"
        "STRICT RULES:\n"
        "1. Follow DISAMBIGUATION — use the correct technical meaning of acronyms.\n"
        "2. Factual claims from SOURCES must cite [S1], [S2], etc.\n"
        "3. Established textbook facts may be stated with tag [FOUNDATIONAL] "
        "(no URL needed) — e.g. standard definitions widely accepted in peer-reviewed ML literature.\n"
        "4. Do NOT invent papers, metrics, or URLs. Do NOT confuse RAG with unrelated acronyms.\n"
        "5. Structure: ### Definition, ### How it works, ### Comparison, ### Applications, ### Sources used\n"
        "6. Target 250–350 words, precise and educational.\n"
    )
    if brief and brief.domain == "machine_learning":
        base += (
            "\nFor deep learning topics: name architectures, training stages, and cite "
            "seminal work when using [FOUNDATIONAL] (e.g. Vaswani 2017 for Transformers, "
            "Lewis et al. 2020 for RAG).\n"
        )
    return base


class ResearcherAgent(BaseAgent):
    agent_type = AgentType.RESEARCHER

    async def run_one(
        self,
        query: str,
        subtask: Subtask,
        use_web_search: bool,
        job_id: UUID,
        on_event: EventCallback | None = None,
        *,
        force_web: bool = False,
        brief: ResearchBrief | None = None,
    ) -> ResearchResult:
        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            f"Researching: {subtask.title}",
            payload={"subtask_id": subtask.id},
        )

        hits = []
        if use_web_search or force_web:
            hits = await gather_evidence(query, subtask.title, brief=brief)

        evidence_block = format_evidence_block(hits)
        sources = [h.url for h in hits]
        context_block = brief.to_prompt_block() if brief else f"TOPIC: {query}"

        user = f"""{context_block}

Subtask: {subtask.title}
Goal: {subtask.description}

SOURCES (web):
{evidence_block}

Write grounded research notes for this subtask."""

        content = await self._invoke(_grounded_system(brief), user)
        return ResearchResult(
            subtask_id=subtask.id,
            raw_content=content,
            sources=sources,
        )

    async def run(
        self,
        query: str,
        subtasks: list[Subtask],
        use_web_search: bool,
        job_id: UUID,
        on_event: EventCallback | None = None,
        max_concurrent: int = 3,
        *,
        force_web: bool = False,
        brief: ResearchBrief | None = None,
    ) -> list[ResearchResult]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            f"Evidence-based research · {len(subtasks)} tracks",
            progress_percent=22,
        )

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded(st: Subtask) -> ResearchResult:
            async with semaphore:
                return await self.run_one(
                    query,
                    st,
                    use_web_search,
                    job_id,
                    on_event,
                    force_web=force_web,
                    brief=brief,
                )

        gathered = await asyncio.gather(
            *[_bounded(st) for st in subtasks],
            return_exceptions=True,
        )

        results: list[ResearchResult] = []
        for i, item in enumerate(gathered):
            if isinstance(item, Exception):
                logger.error("Research failed for %s: %s", subtasks[i].id, item)
                results.append(
                    ResearchResult(
                        subtask_id=subtasks[i].id,
                        raw_content=f"Research incomplete: {item}",
                        sources=[],
                    )
                )
            else:
                results.append(item)

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            f"Collected {len(results)} evidence briefs",
            progress_percent=52,
        )
        return results

    async def run_compact(
        self,
        query: str,
        subtasks: list[Subtask],
        use_web_search: bool,
        job_id: UUID,
        on_event: EventCallback | None = None,
        max_concurrent: int = 2,
        brief: ResearchBrief | None = None,
    ) -> tuple[list[ResearchResult], list[SummaryResult]]:
        results = await self.run(
            query,
            subtasks,
            use_web_search,
            job_id,
            on_event,
            max_concurrent,
            brief=brief,
        )
        summaries = [
            SummaryResult(subtask_id=r.subtask_id, summary=r.raw_content[:600])
            for r in results
        ]
        return results, summaries
