from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.models.schemas import AgentStage, AgentType, ResearchResult, SummaryResult


class ReasonerAgent(BaseAgent):
    agent_type = AgentType.REASONER

    async def run(
        self,
        query: str,
        summaries: list[SummaryResult],
        research_results: list[ResearchResult],
        job_id: UUID,
        on_event: EventCallback | None = None,
    ) -> str:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Cross-validating evidence",
            progress_percent=70,
        )

        summary_block = "\n\n".join(f"### {s.subtask_id}\n{s.summary}" for s in summaries)
        evidence_notes = "\n\n".join(
            f"### {r.subtask_id}\n{r.raw_content[:1500]}\nURLs: {', '.join(r.sources) or 'none'}"
            for r in research_results
        )

        system = (
            "You are a senior research lead (ReAct-style analyst). "
            "Cross-check summaries against raw notes. Output:\n"
            "1. VALIDATED CLAIMS (bullet list, each with [S#] if cited in notes or UNVERIFIED)\n"
            "2. CONFLICTS OR GAPS\n"
            "3. SYNTHESIS (one paragraph, only validated points)\n"
            "Never invent facts. Prefer web-sourced claims."
        )
        user = f"""Question: {query}

Summaries:
{summary_block}

Raw research notes:
{evidence_notes}

Produce validation report:"""

        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            "Resolving conflicts and gaps",
            progress_percent=76,
        )

        reasoning = await self._invoke(system, user)

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            "Evidence validated",
            progress_percent=82,
        )
        return reasoning
