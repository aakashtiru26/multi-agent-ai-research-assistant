from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.models.research_context import ResearchBrief
from app.models.schemas import AgentStage, AgentType, SummaryResult


class SynthesisAgent(BaseAgent):
    agent_type = AgentType.REPORTER

    async def run(
        self,
        query: str,
        summaries: list[SummaryResult],
        reasoning: str,
        source_index: str,
        job_id: UUID,
        on_event: EventCallback | None = None,
        brief: ResearchBrief | None = None,
    ) -> tuple[str, str]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Drafting grounded report",
            progress_percent=84,
            payload={"agent_override": AgentType.REPORTER.value},
        )

        combined = "\n\n".join(f"**{s.subtask_id}**\n{s.summary}" for s in summaries)

        brief_block = brief.to_prompt_block() if brief else ""
        system = (
            "You are an executive research writer (GPT-Researcher / Perplexity style). "
            "Write ONLY from VALIDATED FINDINGS and SUMMARIES. "
            "Keep [S#] and [FOUNDATIONAL] tags. Mark inference as UNVERIFIED:. "
            "550–800 words. Technically precise — correct ML definitions and acronyms."
        )
        user = f"""Question: {query}

{brief_block}

Validation report from lead analyst:
{reasoning[:2500]}

Summaries (with citations):
{combined}

Write markdown report with sections:
## Executive Summary
## Key Findings (bullets with citations)
## Analysis
## Recommendations
## Limitations & Confidence

Append nothing after the report body — sources are added separately."""

        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            "Composing sections",
            progress_percent=88,
        )

        draft = await self._invoke(system, user)
        report = draft.strip()
        if source_index and "## Sources" not in report:
            report = f"{report}\n\n{source_index}"

        reasoning_out = reasoning if reasoning.strip().upper().startswith("REASONING") else (
            f"REASONING:\n{reasoning[:800]}"
        )

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            "Draft report ready",
            progress_percent=90,
        )
        return reasoning_out, report
