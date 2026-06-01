from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.models.schemas import AgentStage, AgentType


class ReporterAgent(BaseAgent):
    agent_type = AgentType.REPORTER

    async def run(
        self,
        query: str,
        reasoning: str,
        job_id: UUID,
        on_event: EventCallback | None = None,
    ) -> str:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Writing final research report",
            progress_percent=90,
        )

        system = (
            "You are a report writer. Create a polished, professional research report "
            "with executive summary, findings, analysis, and recommendations."
        )
        user = f"""Research query: {query}

Reasoning and validated insights:
{reasoning}

Write a complete markdown report with:
# Executive Summary
# Key Findings
# Analysis
# Recommendations
# Conclusion"""

        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            "Generating final report",
            progress_percent=95,
        )

        report = await self._invoke(system, user)

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            "Research report ready",
            progress_percent=100,
        )
        return report
