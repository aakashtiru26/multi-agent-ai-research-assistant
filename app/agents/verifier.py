from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.models.research_context import ResearchBrief
from app.models.schemas import AgentStage, AgentType


class VerifierAgent(BaseAgent):
    agent_type = AgentType.REASONER

    async def run(
        self,
        query: str,
        evidence_pack: str,
        draft_report: str,
        job_id: UUID,
        on_event: EventCallback | None = None,
        brief: ResearchBrief | None = None,
    ) -> tuple[str, bool]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Verifying facts against evidence",
            progress_percent=92,
            payload={"agent_override": "verifier"},
        )

        disambig = ""
        if brief and brief.disambiguation:
            disambig = f"\nMANDATORY INTERPRETATION:\n{brief.disambiguation}\n"

        system = (
            "You are a fact-checking editor for technical research. "
            "Compare DRAFT to EVIDENCE. Remove unsupported claims. "
            "Keep [FOUNDATIONAL] and [S#] tags when valid. "
            "In machine learning, RAG means Retrieval-Augmented Generation — "
            "fix any report that uses the wrong meaning of RAG."
            f"{disambig}"
        )
        user = f"""Question: {query}

EVIDENCE PACK:
{evidence_pack[:6500]}

DRAFT REPORT:
{draft_report[:5500]}

Reply ACCURATE: <report> OR REVISED: <corrected full report>"""

        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            "Correcting errors and acronym misuse",
            progress_percent=96,
            payload={"agent_override": "verifier"},
        )

        raw = await self._invoke(system, user)
        revised = raw.strip().startswith("REVISED:")
        if raw.strip().startswith("ACCURATE:"):
            report = raw.split("ACCURATE:", 1)[-1].strip()
        elif revised:
            report = raw.split("REVISED:", 1)[-1].strip()
        else:
            report = raw.strip()

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            "Verification complete" if not revised else "Report corrected",
            progress_percent=99,
            payload={"agent_override": "verifier", "revised": revised},
        )
        return report, revised
