"""Source retrieval and grounding context (RAG-style evidence pack)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.logging_config import get_logger
from app.models.research_context import ResearchBrief

logger = get_logger(__name__)


@dataclass
class SourceHit:
    source_id: str
    title: str
    snippet: str
    url: str


def format_evidence_block(hits: list[SourceHit]) -> str:
    if not hits:
        return "NO_EXTERNAL_SOURCES_AVAILABLE"
    lines = []
    for h in hits:
        lines.append(
            f"[{h.source_id}] {h.title}\n"
            f"URL: {h.url}\n"
            f"Excerpt: {h.snippet}"
        )
    return "\n\n".join(lines)


def search_web(query: str, max_results: int = 4) -> list[SourceHit]:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        logger.warning("Web search failed for %r: %s", query[:60], exc)
        return []

    hits: list[SourceHit] = []
    for row in rows:
        url = row.get("href", "") or ""
        if not url:
            continue
        hits.append(
            SourceHit(
                source_id="",  # assigned after merge
                title=(row.get("title") or "Untitled")[:200],
                snippet=(row.get("body") or "")[:450],
                url=url,
            )
        )
    return hits


def _merge_hits(all_hits: list[SourceHit], max_total: int = 8) -> list[SourceHit]:
    seen_urls: set[str] = set()
    merged: list[SourceHit] = []
    for hit in all_hits:
        if hit.url in seen_urls:
            continue
        seen_urls.add(hit.url)
        merged.append(hit)
        if len(merged) >= max_total:
            break
    for i, hit in enumerate(merged, start=1):
        hit.source_id = f"S{i}"
    return merged


def multi_search(queries: list[str], per_query: int = 3) -> list[SourceHit]:
    all_hits: list[SourceHit] = []
    for q in queries:
        if q.strip():
            all_hits.extend(search_web(q.strip(), max_results=per_query))
    return _merge_hits(all_hits, max_total=10)


async def gather_evidence(
    query: str,
    subtask_title: str,
    brief: ResearchBrief | None = None,
    max_results: int = 4,
) -> list[SourceHit]:
    queries: list[str] = []
    if brief and brief.search_queries:
        queries.extend(brief.search_queries[:3])
    queries.append(f"{query} {subtask_title}")
    if brief and brief.domain == "machine_learning":
        queries.append(f"{subtask_title} machine learning research")

    queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:5]
    return await asyncio.to_thread(multi_search, queries, per_query=max(2, max_results // 2))


def build_master_source_index(results: list) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for r in results:
        for url in getattr(r, "sources", []) or []:
            if url and url not in seen:
                seen.add(url)
                lines.append(f"- {url}")
    if not lines:
        return "## Sources consulted\nNo external URLs retrieved — report relies on validated model knowledge marked UNVERIFIED where needed."
    return "## Sources consulted\n" + "\n".join(lines)
