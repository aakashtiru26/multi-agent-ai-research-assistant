from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    SUMMARIZER = "summarizer"
    REASONER = "reasoner"
    REPORTER = "reporter"


class AgentStage(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=4000, description="Research question")
    depth: str = Field(default="standard", pattern="^(quick|standard|deep)$")
    use_web_search: bool = Field(default=True, description="Use DuckDuckGo for live research")


class Subtask(BaseModel):
    id: str
    title: str
    description: str
    priority: int = 1


class ResearchResult(BaseModel):
    subtask_id: str
    raw_content: str
    sources: list[str] = Field(default_factory=list)


class SummaryResult(BaseModel):
    subtask_id: str
    summary: str


class ProgressEvent(BaseModel):
    job_id: UUID
    agent: AgentType
    stage: AgentStage
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
    progress_percent: int = Field(default=0, ge=0, le=100)

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class ResearchResponse(BaseModel):
    job_id: UUID
    status: ResearchStatus
    query: str
    research_brief: dict[str, Any] = Field(default_factory=dict)
    plan: list[Subtask] = Field(default_factory=list)
    research_results: list[ResearchResult] = Field(default_factory=list)
    summaries: list[SummaryResult] = Field(default_factory=list)
    reasoning: str = ""
    report: str = ""
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    ollama: dict[str, Any] = Field(default_factory=dict)
    redis: dict[str, Any] = Field(default_factory=dict)
    postgres: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    active_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_jobs: int


def new_job_id() -> UUID:
    return uuid4()
