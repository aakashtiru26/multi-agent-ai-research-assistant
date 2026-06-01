from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.logging_config import get_logger
from app.models.research_context import ResearchBrief
from app.models.schemas import AgentStage, AgentType
from app.services.query_enhancer import default_brief, heuristic_brief, merge_briefs

logger = get_logger(__name__)


class QueryAnalystAgent(BaseAgent):
    """Clarifies intent and search strategy before planning (strong-agent pattern)."""

    agent_type = AgentType.PLANNER

    async def run(
        self,
        query: str,
        job_id: UUID,
        on_event: EventCallback | None = None,
    ) -> ResearchBrief:
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Analyzing question and disambiguating terms",
            progress_percent=2,
            payload={"agent_override": "analyst"},
        )

        hint = heuristic_brief(query)
        llm_brief: ResearchBrief | None = None

        try:
            system = (
                "You are a research query analyst. Disambiguate acronyms (e.g. RAG in ML = "
                "Retrieval-Augmented Generation). Output ONLY valid JSON."
            )
            user = f"""User question: "{query}"

Return JSON:
{{
  "normalized_topic": "clear restatement",
  "disambiguation": "what the user likely means; rule out wrong meanings",
  "domain": "machine_learning|science|business|general",
  "search_queries": ["query1", "query2", "query3"],
  "key_concepts": ["concept1", "concept2"],
  "must_cover": ["point1", "point2"]
}}"""

            raw = await self._invoke(system, user)
            parsed = self.parse_json_block(raw)
            if isinstance(parsed, dict):
                llm_brief = ResearchBrief(
                    normalized_topic=str(parsed.get("normalized_topic", query)),
                    disambiguation=str(parsed.get("disambiguation", "")),
                    domain=str(parsed.get("domain", "general")),
                    search_queries=[str(q) for q in parsed.get("search_queries", []) if q],
                    key_concepts=[str(c) for c in parsed.get("key_concepts", []) if c],
                    must_cover=[str(m) for m in parsed.get("must_cover", []) if m],
                )
        except Exception as exc:
            logger.warning("Query analyst LLM failed: %s", exc)

        brief = merge_briefs(hint, llm_brief, query)
        if not brief.normalized_topic:
            brief = default_brief(query)
        if hint and not brief.disambiguation:
            brief.disambiguation = hint.disambiguation

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            f"Topic: {brief.normalized_topic[:60]}",
            progress_percent=8,
            payload={"agent_override": "analyst", "domain": brief.domain},
        )
        return brief
