from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent, EventCallback
from app.config import Settings
from app.logging_config import get_logger
from app.models.research_context import ResearchBrief
from app.models.schemas import AgentStage, AgentType, ProgressEvent, Subtask

logger = get_logger(__name__)


class PlannerAgent(BaseAgent):
    agent_type = AgentType.PLANNER

    def __init__(self, llm: Any, settings: Settings) -> None:
        super().__init__(llm)
        self._settings = settings

    def subtask_count_for_depth(self, depth: str) -> int:
        counts = {"quick": 2, "standard": 3, "deep": self._settings.max_subtasks}
        return min(counts.get(depth, 3), self._settings.max_subtasks)

    async def run(
        self,
        query: str,
        depth: str,
        job_id: UUID,
        on_event: EventCallback | None = None,
        *,
        use_llm: bool | None = None,
        brief: ResearchBrief | None = None,
    ) -> list[Subtask]:
        count = self.subtask_count_for_depth(depth)
        plan_query = brief.normalized_topic if brief and brief.normalized_topic else query
        await self._emit(
            on_event,
            job_id,
            AgentStage.STARTED,
            "Planning research strategy",
            progress_percent=5,
        )

        should_use_llm = (
            use_llm if use_llm is not None else self._settings.use_llm_planner
        ) and not self._settings.turbo_pipeline

        if should_use_llm:
            subtasks = await self._plan_with_retries(
                plan_query, count, job_id, on_event, brief=brief
            )
        else:
            await self._emit(
                on_event,
                job_id,
                AgentStage.IN_PROGRESS,
                f"Structured plan · {count} focus areas",
                progress_percent=12,
            )
            subtasks = self._fallback_subtasks(plan_query, count, brief=brief)

        await self._emit(
            on_event,
            job_id,
            AgentStage.COMPLETED,
            f"Plan ready · {len(subtasks)} subtasks",
            progress_percent=18,
            payload={"subtasks": [s.model_dump() for s in subtasks]},
        )
        return subtasks

    async def _plan_with_retries(
        self,
        query: str,
        count: int,
        job_id: UUID,
        on_event: EventCallback | None,
        brief: ResearchBrief | None = None,
    ) -> list[Subtask]:
        await self._emit(
            on_event,
            job_id,
            AgentStage.IN_PROGRESS,
            f"Designing {count} targeted subtasks",
            progress_percent=10,
        )
        system = (
            "You are a senior research planner. Break queries into distinct, "
            "answerable subtasks. Output ONLY a JSON array with id, title, description, priority."
        )
        brief_ctx = f"\n{brief.to_prompt_block()}\n" if brief else ""
        user = (
            f'Research question: "{query}"\n{brief_ctx}'
            f"Create exactly {count} non-overlapping subtasks.\n"
            f'[{{"id":"task-1","title":"...","description":"Specific angle to investigate","priority":1}}]'
        )
        try:
            raw = await self._invoke(system, user)
            items = self._extract_items(raw)
            if items:
                return self._to_subtasks(items, count)
        except Exception as exc:
            logger.warning("Planner LLM failed: %s", exc)
        return self._fallback_subtasks(query, count, brief=brief)

    def _extract_items(self, raw: str) -> list[dict[str, Any]]:
        parsed = self.parse_json_block(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            for key in ("subtasks", "tasks", "items", "plan"):
                nested = parsed.get(key)
                if isinstance(nested, list):
                    return [x for x in nested if isinstance(x, dict)]
            return [parsed]
        return []

    def _to_subtasks(self, items: list[dict[str, Any]], count: int) -> list[Subtask]:
        subtasks: list[Subtask] = []
        for i, item in enumerate(items[:count]):
            subtasks.append(
                Subtask(
                    id=str(item.get("id", f"task-{i + 1}")),
                    title=str(item.get("title", f"Research area {i + 1}"))[:120],
                    description=str(
                        item.get("description", item.get("desc", ""))
                    )[:500],
                    priority=int(item.get("priority", i + 1)),
                )
            )
        return subtasks

    @staticmethod
    def _fallback_subtasks(
        query: str, count: int, brief: ResearchBrief | None = None
    ) -> list[Subtask]:
        if brief and brief.must_cover:
            return [
                Subtask(
                    id=f"task-{i + 1}",
                    title=brief.must_cover[i][:80],
                    description=brief.must_cover[i],
                    priority=i + 1,
                )
                for i in range(min(count, len(brief.must_cover)))
            ]
        templates = [
            ("Background & definitions", f"Core concepts, scope, and context for: {query}"),
            ("Evidence & comparison", f"Data, comparisons, and expert views on: {query}"),
            ("Implications & recommendations", f"Practical impact and best actions for: {query}"),
            ("Risks & open questions", f"Limitations, risks, and gaps related to: {query}"),
        ]
        return [
            Subtask(
                id=f"task-{i + 1}",
                title=templates[i % len(templates)][0],
                description=templates[i % len(templates)][1],
                priority=i + 1,
            )
            for i in range(count)
        ]
