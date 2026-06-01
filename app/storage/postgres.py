import json
from uuid import UUID

from sqlalchemy import Column, DateTime, String, Text, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings
from app.logging_config import get_logger
from app.models.schemas import ResearchResponse, ResearchStatus

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class ResearchJobRow(Base):
    __tablename__ = "research_jobs"

    job_id = Column(PGUUID(as_uuid=True), primary_key=True)
    status = Column(String(32), nullable=False)
    query = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PostgresStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine = create_async_engine(settings.postgres_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def connect(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Postgres tables ready")

    async def disconnect(self) -> None:
        await self._engine.dispose()

    async def health(self) -> dict:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(select(1))
            return {"status": "healthy", "reachable": True}
        except Exception as exc:
            return {"status": "unhealthy", "reachable": False, "error": str(exc)}

    async def save_job(self, job: ResearchResponse) -> None:
        async with self._session_factory() as session:
            row = ResearchJobRow(
                job_id=job.job_id,
                status=job.status.value,
                query=job.query,
                payload=job.model_dump_json(),
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
            await session.merge(row)
            await session.commit()

    async def get_job(self, job_id: UUID) -> ResearchResponse | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ResearchJobRow).where(ResearchJobRow.job_id == job_id)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return ResearchResponse.model_validate(json.loads(row.payload))
