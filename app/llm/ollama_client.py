"""LLM factory — supports Groq (cloud, free) and Ollama (local).

Set LLM_BACKEND=groq  + GROQ_API_KEY in .env for cloud deployment.
Set LLM_BACKEND=ollama for local development with Ollama.
"""

from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class OllamaLLMFactory:
    """Unified LLM factory — name kept for backward compatibility with pipeline.py."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(
        self,
        temperature: float = 0.3,
        *,
        num_predict: int | None = None,
        response_format: str | None = None,
    ) -> BaseChatModel:
        if self._settings.using_groq:
            return self._create_groq(temperature)
        return self._create_ollama(temperature, num_predict=num_predict, response_format=response_format)

    def create_report(self, temperature: float = 0.35) -> BaseChatModel:
        if self._settings.using_groq:
            return self._create_groq(temperature)
        return self._create_ollama(
            temperature,
            num_predict=self._settings.ollama_num_predict_report,
        )

    # ── Groq ──────────────────────────────────────────────────────────────────
    def _create_groq(self, temperature: float) -> BaseChatModel:
        from langchain_groq import ChatGroq

        api_key = self._settings.groq_api_key.get_secret_value()
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
            )
        return ChatGroq(
            api_key=api_key,
            model=self._settings.groq_model,
            temperature=temperature,
            max_tokens=2048,
        )

    # ── Ollama ────────────────────────────────────────────────────────────────
    def _create_ollama(
        self,
        temperature: float,
        *,
        num_predict: int | None = None,
        response_format: str | None = None,
    ) -> BaseChatModel:
        from langchain_ollama import ChatOllama

        predict = num_predict or self._settings.ollama_num_predict_fast
        kwargs: dict = {
            "base_url": self._settings.ollama_base_url,
            "model": self._settings.ollama_model,
            "temperature": temperature,
            "timeout": self._settings.ollama_timeout,
            "num_predict": predict,
        }
        if response_format:
            kwargs["format"] = response_format
        return ChatOllama(**kwargs)


# ── Health checks ─────────────────────────────────────────────────────────────

async def check_ollama_health(settings: Settings) -> dict[str, Any]:
    """Health check — works for both Groq and Ollama backends."""
    if settings.using_groq:
        return await _check_groq_health(settings)
    return await _check_ollama_health(settings)


async def _check_groq_health(settings: Settings) -> dict[str, Any]:
    api_key = settings.groq_api_key.get_secret_value()
    if not api_key:
        return {
            "status": "unhealthy",
            "reachable": False,
            "backend": "groq",
            "error": "GROQ_API_KEY not set",
            "configured_model": settings.groq_model,
            "model_available": False,
        }
    # Lightweight check — just verify the key is non-empty and the API is reachable
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            models = [m.get("id", "") for m in resp.json().get("data", [])]
            model_available = any(settings.groq_model in m for m in models)
            return {
                "status": "healthy" if model_available else "degraded",
                "reachable": True,
                "backend": "groq",
                "configured_model": settings.groq_model,
                "model_available": model_available,
                "available_models": models[:10],
            }
    except Exception as exc:
        logger.warning("Groq health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "reachable": False,
            "backend": "groq",
            "error": str(exc),
            "configured_model": settings.groq_model,
            "model_available": False,
        }


async def _check_ollama_health(settings: Settings) -> dict[str, Any]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            configured = settings.ollama_model
            model_available = any(configured in m for m in models)
            return {
                "status": "healthy" if model_available else "degraded",
                "reachable": True,
                "backend": "ollama",
                "configured_model": configured,
                "model_available": model_available,
                "available_models": models[:10],
            }
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "reachable": False,
            "backend": "ollama",
            "error": str(exc),
            "configured_model": settings.ollama_model,
            "model_available": False,
        }
