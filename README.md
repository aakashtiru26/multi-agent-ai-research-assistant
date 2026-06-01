# Multi-Agent AI Research Assistant

A research automation tool I built to explore multi-agent LLM systems. You type a question, and a pipeline of specialized agents — planner, researcher, summarizer, reasoner, reporter, and verifier — work through it and hand you back a structured report. The whole thing streams live so you can watch each agent do its job in real time.

Built with FastAPI, LangChain, and Groq (or Ollama locally). Deployed on Render.

**Live demo:** https://multi-agent-ai-research-assistant-qp6w.onrender.com

---

## What it does

You submit a research query with a depth setting (Quick / Standard / Deep). The pipeline kicks off:

1. **Query Analyst** — figures out what you're actually asking, disambiguates terms
2. **Planner** — breaks the query into focused subtasks
3. **Researcher** — pulls web results via DuckDuckGo and writes grounded notes per subtask
4. **Summarizer** — condenses each research block, keeps citations intact
5. **Reasoner** — cross-checks everything, flags conflicts, builds a validated synthesis
6. **Reporter** — writes the final markdown report from validated findings
7. **Verifier** — fact-checks the draft against the original evidence before delivery

Progress streams to the UI via SSE so you see each agent activate in real time.

---

## Tech stack

- **Backend** — Python 3.12, FastAPI, LangChain
- **LLM** — Groq API (`llama-3.3-70b-versatile`) for cloud, Ollama for local dev
- **Web search** — DuckDuckGo (no API key needed)
- **Frontend** — Vanilla HTML/CSS/JS, claymorphism UI, fully responsive
- **Deployment** — Docker, Render

---

## Running locally

You need Python 3.11+ and either a Groq API key (free at [console.groq.com](https://console.groq.com)) or Ollama installed.

```bash
git clone https://github.com/aakashtiru26/multi-agent-ai-research-assistant.git
cd multi-agent-ai-research-assistant

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Open .env and add your GROQ_API_KEY
```

**With Groq (recommended):**
```bash
# In .env set:
# LLM_BACKEND=groq
# GROQ_API_KEY=your-key-here

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**With Ollama (local, no API key):**
```bash
ollama pull llama3.2:1b

# In .env set:
# LLM_BACKEND=ollama

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — the dashboard loads straight away, no login needed.

---

## Environment variables

Copy `.env.example` to `.env` and fill these in:

| Variable | Description |
|---|---|
| `LLM_BACKEND` | `groq` or `ollama` |
| `GROQ_API_KEY` | Your Groq API key |
| `GROQ_MODEL` | Model to use, e.g. `llama-3.3-70b-versatile` |
| `API_KEY` | Server-side key for external API calls |
| `MAX_SUBTASKS` | How many subtasks the planner creates (default 4) |
| `ENABLE_VERIFIER` | Run the fact-check pass — `true` or `false` |

The dashboard at `/` doesn't need an API key. The `API_KEY` is only for hitting `/research` directly via curl or scripts.

---

## API

Two route prefixes — one open for the dashboard, one key-protected for external use:

| Prefix | Auth | Purpose |
|---|---|---|
| `/ui/research` | None | Used by the web dashboard |
| `/research` | `X-API-Key` header | External scripts, integrations |

```bash
# Start a research job
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"query": "How does RAG reduce hallucinations?", "depth": "standard", "use_web_search": true}'

# Stream progress
curl -N http://localhost:8000/research/<job_id>/stream \
  -H "X-API-Key: your-api-key"

# Get final report
curl http://localhost:8000/research/<job_id> \
  -H "X-API-Key: your-api-key"
```

Health check: `GET /health` — shows LLM backend status, model availability, Redis/Postgres if enabled.

---

## Project layout

```
├── app/
│   ├── agents/          # one file per agent (planner, researcher, etc.)
│   ├── api/             # FastAPI routes, middleware, deps
│   ├── llm/             # LLM factory — switches between Groq and Ollama
│   ├── models/          # Pydantic schemas
│   ├── orchestration/   # pipeline runner + in-memory job store
│   └── services/        # web search, query enhancement, research service
├── frontend/            # HTML + CSS + JS dashboard
├── tests/
├── Dockerfile
├── render.yaml          # one-click Render deploy config
└── .env.example
```

---

## Deploying to Render

The repo includes a `render.yaml` so Render picks up the config automatically.

1. Fork or clone this repo to your GitHub
2. Go to [render.com](https://render.com) → New Web Service → connect your repo
3. Add these as environment variables in the Render dashboard:
   - `GROQ_API_KEY` — your Groq key (mark as secret)
   - `API_KEY` — any random string
4. Hit deploy — takes about 3-4 minutes

Every push to `main` triggers an automatic redeploy.

---

## Things I learned building this

- Chaining LLM agents sequentially vs concurrently has a big impact on both quality and rate limit behaviour — running subtasks one at a time produces more coherent output and avoids 429s on free tiers
- SSE is simpler than WebSockets for one-way streaming and works well for this use case
- Groq's free tier is fast but token-limited — `llama-3.1-8b-instant` has a much higher daily token allowance than the 70b model if you need more throughput
- Keeping the frontend as plain HTML/CSS/JS with no build step makes deployment significantly simpler

---

## License

MIT
