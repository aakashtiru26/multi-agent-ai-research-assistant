from datetime import datetime, timezone
from uuid import UUID

from app.agents import (
    PlannerAgent,
    ReasonerAgent,
    ResearcherAgent,
    SummarizerAgent,
)
from app.agents.base import EventCallback
from app.agents.query_analyst import QueryAnalystAgent
from app.agents.synthesis import SynthesisAgent
from app.agents.verifier import VerifierAgent
from app.config import Settings
from app.llm.ollama_client import OllamaLLMFactory
from app.logging_config import get_logger
from app.models.research_context import ResearchBrief
from app.models.schemas import (
    AgentStage,
    AgentType,
    ProgressEvent,
    ResearchRequest,
    ResearchResponse,
    ResearchStatus,
)
from app.orchestration.state import JobStore
from app.services.retrieval import build_master_source_index

logger = get_logger(__name__)


class ResearchPipeline:
    def __init__(self, settings: Settings, job_store: JobStore) -> None:
        self._settings = settings
        self._job_store = job_store
        self._turbo = settings.turbo_pipeline
        llm_factory = OllamaLLMFactory(settings)

        llm_precise = llm_factory.create(temperature=0.15)
        planner_llm = llm_factory.create(temperature=0.05, response_format="json")
        analyst_llm = llm_factory.create(temperature=0.05, response_format="json")
        report_llm = llm_factory.create_report(temperature=0.2)

        self._analyst = QueryAnalystAgent(analyst_llm)
        self._planner = PlannerAgent(planner_llm, settings)
        self._researcher = ResearcherAgent(llm_precise)
        self._summarizer = SummarizerAgent(llm_precise)
        self._reasoner = ReasonerAgent(llm_precise)
        self._synthesis = SynthesisAgent(report_llm)
        self._verifier = VerifierAgent(llm_precise)

    def _make_callback(self, job_id: UUID) -> EventCallback:
        async def on_event(event: ProgressEvent) -> None:
            await self._job_store.publish(event)

        return on_event

    def _build_evidence_pack(self, job: ResearchResponse, brief: ResearchBrief | None) -> str:
        parts = [f"QUESTION: {job.query}", ""]
        if brief:
            parts.append(brief.to_prompt_block())
            parts.append("")
        for r in job.research_results:
            parts.append(f"--- {r.subtask_id} ---")
            parts.append(r.raw_content)
            if r.sources:
                parts.append("URLs: " + ", ".join(r.sources))
            parts.append("")
        for s in job.summaries:
            parts.append(f"Summary {s.subtask_id}: {s.summary}")
        if job.reasoning:
            parts.append(f"\nValidation:\n{job.reasoning}")
        return "\n".join(parts)

    async def execute(self, job_id: UUID, request: ResearchRequest) -> ResearchResponse:
        job = await self._job_store.get(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job.status = ResearchStatus.RUNNING
        await self._job_store.update(job)
        callback = self._make_callback(job_id)
        force_web = self._settings.require_web_search or request.use_web_search

        try:
            brief = await self._analyst.run(request.query, job_id, callback)
            job.research_brief = brief.model_dump()
            await self._job_store.update(job)

            plan = await self._planner.run(
                request.query, request.depth, job_id, callback, brief=brief
            )
            job.plan = plan
            await self._job_store.update(job)

            topic = brief.normalized_topic or request.query

            if self._turbo:
                research_results, summaries = await self._researcher.run_compact(
                    topic,
                    plan,
                    request.use_web_search,
                    job_id,
                    callback,
                    max_concurrent=self._settings.max_concurrent_research,
                    brief=brief,
                )
                job.research_results = research_results
                job.summaries = summaries
            else:
                research_results = await self._researcher.run(
                    topic,
                    plan,
                    request.use_web_search,
                    job_id,
                    callback,
                    max_concurrent=self._settings.max_concurrent_research,
                    force_web=force_web,
                    brief=brief,
                )
                job.research_results = research_results
                await self._job_store.update(job)

                summaries = await self._summarizer.run(
                    research_results, job_id, callback, batch=True
                )
                job.summaries = summaries

            await self._job_store.update(job)

            reasoning = await self._reasoner.run(
                request.query,
                job.summaries,
                job.research_results,
                job_id,
                callback,
            )
            job.reasoning = reasoning
            await self._job_store.update(job)

            source_index = build_master_source_index(job.research_results)
            _, draft_report = await self._synthesis.run(
                request.query,
                job.summaries,
                reasoning,
                source_index,
                job_id,
                callback,
                brief=brief,
            )

            if self._settings.enable_verifier and not self._turbo:
                evidence_pack = self._build_evidence_pack(job, brief)
                final_report, _ = await self._verifier.run(
                    request.query,
                    evidence_pack,
                    draft_report,
                    job_id,
                    callback,
                    brief=brief,
                )
                job.report = final_report
            else:
                job.report = draft_report

            job.status = ResearchStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            await self._job_store.update(job)
            await self._job_store.mark_finished(job_id, success=True)
            logger.info("Job %s completed", job_id)
            return job

        except Exception as exc:
            logger.exception("Job %s failed: %s", job_id, exc)
            job.status = ResearchStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await self._job_store.update(job)
            await self._job_store.mark_finished(job_id, success=False)
            await self._job_store.publish(
                ProgressEvent(
                    job_id=job_id,
                    agent=AgentType.PLANNER,
                    stage=AgentStage.FAILED,
                    message=f"Pipeline failed: {exc}",
                )
            )
            raise
        finally:
            await self._job_store.close_subscribers(job_id)
