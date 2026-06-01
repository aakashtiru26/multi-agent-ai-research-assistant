import pytest

HEADERS = {"X-API-Key": "test-api-key"}


@pytest.mark.asyncio
async def test_liveness(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["alive"] is True


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "ollama" in body


@pytest.mark.asyncio
async def test_metrics(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data


@pytest.mark.asyncio
async def test_unauthorized_research(client):
    response = await client.post("/research", json={"query": "test query here"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_research_accepted(client):
    response = await client.post(
        "/research",
        json={"query": "Impact of transformer models on NLP", "depth": "quick"},
        headers=HEADERS,
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] in {"pending", "running", "completed", "failed"}
