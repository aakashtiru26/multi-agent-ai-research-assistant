from app.models.schemas import ProgressEvent, ResearchRequest, Subtask
from app.models.schemas import AgentStage, AgentType
from uuid import uuid4


def test_research_request_validation():
    req = ResearchRequest(query="What is RAG?", depth="standard")
    assert req.use_web_search is True


def test_progress_event_sse():
    event = ProgressEvent(
        job_id=uuid4(),
        agent=AgentType.PLANNER,
        stage=AgentStage.STARTED,
        message="Planning",
        progress_percent=10,
    )
    assert event.to_sse().startswith("data: ")


def test_subtask_model():
    st = Subtask(id="t1", title="Topic", description="Details")
    assert st.priority == 1
