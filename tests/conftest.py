import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("POSTGRES_ENABLED", "false")

from app.config import get_settings

get_settings.cache_clear()

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
