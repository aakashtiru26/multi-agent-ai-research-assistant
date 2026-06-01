import json
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.logging_config import get_logger
from app.models.schemas import AgentStage, AgentType, ProgressEvent

logger = get_logger(__name__)

EventCallback = Callable[[ProgressEvent], Awaitable[None]]


class BaseAgent(ABC):
    agent_type: AgentType

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        ...

    async def _invoke(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self._llm.ainvoke(messages)
        content = response.content
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()

    async def _emit(
        self,
        callback: EventCallback | None,
        job_id: Any,
        stage: AgentStage,
        message: str,
        progress_percent: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if callback is None:
            return
        event = ProgressEvent(
            job_id=job_id,
            agent=self.agent_type,
            stage=stage,
            message=message,
            progress_percent=progress_percent,
            payload=payload or {},
        )
        await callback(event)

    @staticmethod
    def parse_json_block(text: str) -> Any:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence:
            text = fence.group(1).strip()
        text = re.sub(r",\s*([\]}])", r"\1", text)

        attempts = [text]
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            attempts.append(text[start : end + 1])
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            attempts.append(text[start : end + 1])

        for candidate in attempts:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        objects = re.findall(r"\{[^{}]*\}", text, re.DOTALL)
        if objects:
            parsed_objects = []
            for obj in objects:
                try:
                    parsed_objects.append(json.loads(obj))
                except json.JSONDecodeError:
                    continue
            if parsed_objects:
                return parsed_objects

        raise json.JSONDecodeError("Could not parse JSON from model output", text, 0)
