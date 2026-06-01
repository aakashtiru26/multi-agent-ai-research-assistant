# MultiAI Research Assistant

A production-oriented **multi-agent research pipeline** built with Python, FastAPI, LangChain, and Ollama. Users submit a research query; specialized agents plan, research, summarize, reason, and write a final report while the UI streams progress in real time.

## Architecture

```
┌─────────────┐     REST/SSE/WS      ┌──────────────────────────────────────────┐
│  Dashboard  │ ◄──────────────────► │              FastAPI API                    │
│  (frontend) │                      │  auth · health · metrics · research jobs  │
└─────────────┘                      └──────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                                         ┌────────────────────────┐
                                         │   ResearchPipeline      │
                                         │   (orchestrator)        │
                                         └───────────┬────────────┘
                                                     │
     ┌───────────┬───────────┬───────────┬───────────┴───────────┐
     ▼           ▼           ▼           ▼                       ▼
 Planner    Researcher   Summarizer   Reasoner              Reporter
     │           │           │           │                       │
     └───────────┴───────────┴───────────┴───────────────────────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │   Ollama    │  (local LLM via LangChain)
                          └─────────────┘

Optional: Redis (result cache) · Postgres (job persistence)
```

### Agent flow

1. **Planner** — decomposes the query into subtasks (count depends on `depth`)
2. **Researcher** — runs subtasks concurrently; optional DuckDuckGo web search
3. **Summarizer** — condenses each research block
4. **Reasoner** — cross-validates and merges insights
5. **Reporter** — produces the final markdown report

Progress events are published to an in-memory pub/sub (`JobStore`) and streamed via **SSE** or **WebSocket**.

## Project structure

```
MultiAI_RAG_Agent/
├── app/
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Pydantic settings
│   ├── logging_config.py
│   ├── api/                    # routes, middleware, deps
│   ├── agents/                 # planner, researcher, ...
│   ├── llm/                    # Ollama + LangChain
│   ├── models/                 # Pydantic schemas
│   ├── orchestration/          # pipeline + job store
│   ├── services/               # research service
│   └── storage/                # optional Redis / Postgres
├── frontend/                   # dashboard (HTML/CSS/JS)
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) running locally (or via Docker)
- A pulled model, e.g. `ollama pull llama3.2`

## Run locally

```bash
cd MultiAI_RAG_Agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set API_KEY and OLLAMA_MODEL

# Terminal 1: ensure Ollama is running
ollama serve
ollama pull llama3.2

# Terminal 2: API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** for the dashboard (no API key required), or **http://localhost:8000/docs** for OpenAPI.

## How to get your API key (step by step)

The API key lives **only on the server** in `.env`. The dashboard does not ask for it. You need the key only for **external** calls (curl, Postman, another service) to `/research`.

1. **Go to the project folder**
   ```bash
   cd MultiAI_RAG_Agent
   ```

2. **Create your environment file** (if you have not already)
   ```bash
   cp .env.example .env
   ```

3. **Open `.env` in any editor**
   ```bash
   nano .env
   # or: code .env
   ```

4. **Find the line `API_KEY=...`** — that value is your API key.  
   Example default: `API_KEY=dev-secret-change-me`

5. **(Recommended for production) Generate a strong key** and replace that line:
   ```bash
   openssl rand -hex 32
   ```
   Copy the output into `.env`:
   ```env
   API_KEY=paste-the-long-random-string-here
   ```

6. **Restart the API** so it loads the new value:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   Or with Docker: `docker compose up -d --build`

7. **Use the key in HTTP requests** to protected routes (`/research`, not `/ui/research`):
   ```bash
   curl -H "X-API-Key: YOUR_VALUE_FROM_ENV" ...
   ```

**Important:** Do not commit `.env` to git. Do not put the key in frontend code — the browser uses `/ui/research`, which is open to same-origin dashboard traffic only.

### Optional Redis / Postgres

Set in `.env`:

```env
REDIS_ENABLED=true
POSTGRES_ENABLED=true
```

Start dependencies:

```bash
docker compose --profile full up -d redis postgres
```

## Deploy with Docker

```bash
cp .env.example .env
docker compose up -d --build

# Pull model into Ollama container (first time)
docker compose exec ollama ollama pull llama3.2
```

Services:

| Service  | URL                    |
|----------|------------------------|
| API + UI | http://localhost:8000  |
| Ollama   | http://localhost:11434 |

Full stack with Redis and Postgres:

```bash
docker compose --profile full up -d --build
```

Enable in `.env`:

```env
REDIS_ENABLED=true
POSTGRES_ENABLED=true
```

## API reference

| Prefix | Auth | Used by |
|--------|------|---------|
| `/ui/research` | None | Web dashboard (same server) |
| `/research` | `X-API-Key` header | curl, scripts, integrations |

Protected routes require: `X-API-Key: <value of API_KEY in your .env>`

### Health & monitoring

| Method | Path            | Auth | Description        |
|--------|-----------------|------|--------------------|
| GET    | `/health`       | No   | Full health status |
| GET    | `/health/live`  | No   | Liveness probe     |
| GET    | `/health/ready` | No   | Readiness (Ollama) |
| GET    | `/metrics`      | No   | Job counters       |

### Research (external API — requires API key)

| Method | Path                      | Description              |
|--------|---------------------------|--------------------------|
| POST   | `/research`               | Start job (202)          |
| GET    | `/research/{job_id}`      | Get job result           |
| GET    | `/research/{job_id}/stream` | SSE progress stream    |
| WS     | `/research/{job_id}/ws`   | WebSocket progress       |

### Research (dashboard — no API key)

Same paths under `/ui/research` (e.g. `POST /ui/research`).

## Example API calls

### Start research

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-change-me" \
  -d '{
    "query": "Compare RAG vs fine-tuning for enterprise knowledge bases",
    "depth": "standard",
    "use_web_search": true
  }'
```

Response:

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "query": "Compare RAG vs fine-tuning..."
}
```

### Stream progress (SSE)

```bash
curl -N http://localhost:8000/research/<JOB_ID>/stream \
  -H "X-API-Key: dev-secret-change-me"
```

### Get final result

```bash
curl http://localhost:8000/research/<JOB_ID> \
  -H "X-API-Key: dev-secret-change-me"
```

### WebSocket

```javascript
const ws = new WebSocket(
  "ws://localhost:8000/research/<JOB_ID>/ws?api_key=dev-secret-change-me"
);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

## Example queries

- *What are the main approaches to multi-agent LLM orchestration in 2025?*
- *Compare vector databases (Chroma, Pinecone, pgvector) for RAG at scale*
- *Summarize security best practices for deploying local LLMs with Ollama*
- *How does retrieval-augmented generation reduce hallucinations in legal tech?*

Use `depth`: `quick` (2 subtasks), `standard` (4), or `deep` (up to `MAX_SUBTASKS`).

## Tests

```bash
pip install -r requirements.txt
pytest -v
```

Integration tests that call Ollama are not included by default; unit tests cover API auth, health, and schemas.

## Configuration

See `.env.example` for all variables. Important:

| Variable         | Default              | Description              |
|------------------|----------------------|--------------------------|
| `API_KEY`        | —                    | Required for `/research` |
| `OLLAMA_BASE_URL`| `http://localhost:11434` | Ollama endpoint      |
| `OLLAMA_MODEL`   | `llama3.2`           | Model name               |
| `MAX_SUBTASKS`   | `5`                  | Cap for deep research    |
| `LOG_LEVEL`      | `INFO`               | Logging verbosity        |

## Security notes

- Change `API_KEY` in production.
- Restrict CORS in production (`DEBUG=false`).
- Do not expose Ollama publicly without authentication.
- Store secrets in environment variables or a secrets manager, not in git.

## License

MIT
