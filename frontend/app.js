"use strict";

const API_BASE = "/ui/research";
const AGENTS   = ["planner", "researcher", "summarizer", "reasoner", "reporter", "verifier"];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const queryInput     = document.getElementById("query");
const depthSelect    = document.getElementById("depth");
const webSearchCheck = document.getElementById("webSearch");
const startBtn       = document.getElementById("startBtn");
const eventLog       = document.getElementById("eventLog");
const progressFill   = document.getElementById("progressFill");
const progressPct    = document.getElementById("progressPct");
const progressBar    = document.getElementById("progressBar");
const reportEl       = document.getElementById("report");
const reportEmpty    = document.getElementById("reportEmpty");
const reportSkeleton = document.getElementById("reportSkeleton");
const reportSection  = document.getElementById("reportSection");
const agentSteps     = document.getElementById("agentSteps");

const stepEls = Object.fromEntries(
  [...agentSteps.querySelectorAll(".step")].map((el) => [el.dataset.agent, el])
);

// ── Helpers ───────────────────────────────────────────────────────────────────
function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function setLoading(loading) {
  startBtn.disabled = loading;
  startBtn.classList.toggle("is-loading", loading);
  startBtn.querySelector(".btn-loader").hidden = !loading;
}

function resolveAgent(data) {
  const override = data.payload?.agent_override;
  if (override === "analyst") return "planner";
  if (override) return override;
  if (data.agent) return String(data.agent).toLowerCase();
  return "system";
}

function setProgress(pct) {
  const n = Math.min(100, Math.max(0, pct || 0));
  progressFill.style.width = `${n}%`;
  progressPct.textContent  = `${n}%`;
  progressBar.setAttribute("aria-valuenow", n);
}

function setStepState(agent, state) {
  const el = stepEls[agent];
  if (!el) return;
  el.classList.remove("active", "done", "failed");
  if (state) el.classList.add(state);
}

function resetPipeline() {
  AGENTS.forEach((a) => setStepState(a, null));
  setProgress(0);
  eventLog.innerHTML = "";
  reportEl.classList.remove("visible");
  reportEl.innerHTML = "";
  reportEmpty.hidden = false;
  reportSkeleton.hidden = true;
  reportSection.classList.remove("is-generating");
}

// ── Event log — only key milestones ──────────────────────────────────────────
const KEY_STAGES = new Set(["started", "completed", "failed"]);

function logEvent(data) {
  const agent = resolveAgent(data);
  const stage = data.stage || "";

  // Update step indicators regardless of whether we log
  if (AGENTS.includes(agent)) {
    if (stage === "started" || stage === "in_progress") setStepState(agent, "active");
    if (stage === "completed") setStepState(agent, "done");
    if (stage === "failed")    setStepState(agent, "failed");
  }

  if (agent === "reporter" && (stage === "started" || stage === "in_progress")) {
    showReportLoading();
  }

  if (data.progress_percent != null) setProgress(data.progress_percent);

  // Only surface key milestones in the log
  if (!KEY_STAGES.has(stage) && agent !== "system") return;

  const li = document.createElement("li");
  li.className = stage ? `stage-${stage}` : "";
  li.innerHTML = `<span class="agent-tag">${escapeHtml(agent)}</span><span class="msg">${escapeHtml(data.message || "")}</span>`;
  eventLog.prepend(li);
}

// ── Report rendering ──────────────────────────────────────────────────────────
function showReportLoading() {
  reportEmpty.hidden = true;
  reportEl.classList.remove("visible");
  reportSkeleton.hidden = false;
  reportSection.classList.add("is-generating");
  reportSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderReport(markdown) {
  reportSkeleton.hidden = true;
  reportSection.classList.remove("is-generating");
  reportEmpty.hidden = true;
  const html =
    typeof marked !== "undefined"
      ? marked.parse(markdown, { breaks: true })
      : `<pre>${escapeHtml(markdown)}</pre>`;
  reportEl.innerHTML = html;
  reportEl.classList.add("visible");
  reportSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Research flow ─────────────────────────────────────────────────────────────
async function startResearch() {
  const query = queryInput.value.trim();
  if (!query) { queryInput.focus(); return; }

  resetPipeline();
  setLoading(true);

  try {
    const res = await fetch(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        depth: depthSelect.value,
        use_web_search: webSearchCheck.checked,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }

    const job = await res.json();
    logEvent({ type: "system", message: "Research job started", progress_percent: 2 });
    streamJob(job.job_id);
  } catch (e) {
    logEvent({ type: "system", message: e.message, stage: "failed" });
    setLoading(false);
  }
}

function streamJob(jobId) {
  fetch(`${API_BASE}/${jobId}/stream`, {
    headers: { Accept: "text/event-stream" },
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(await res.text());

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "done") {
              await fetchReport(jobId);
              setLoading(false);
              return;
            }
            if (data.type === "report") {
              renderReport(data.report);
              setProgress(100);
              setLoading(false);
              return;
            }
            if (data.type !== "connected") logEvent(data);
          } catch { /* keepalive / malformed */ }
        }
      }
      setLoading(false);
    })
    .catch((e) => {
      logEvent({ type: "system", message: `Stream error: ${e.message}`, stage: "failed" });
      setLoading(false);
    });
}

async function fetchReport(jobId) {
  const res = await fetch(`${API_BASE}/${jobId}`);
  if (!res.ok) return;
  const job = await res.json();
  if (job.report) {
    renderReport(job.report);
    setProgress(100);
    AGENTS.forEach((a) => setStepState(a, "done"));
  } else if (job.error) {
    reportSkeleton.hidden = true;
    reportEmpty.hidden = false;
    reportEmpty.querySelector("p").textContent = job.error;
  }
}

// ── Event listeners ───────────────────────────────────────────────────────────
startBtn.addEventListener("click", startResearch);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) startResearch();
});
