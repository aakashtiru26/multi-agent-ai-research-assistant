"""Heuristic query expansion for technical topics (reduces wrong answers on acronyms)."""

from __future__ import annotations

import re

from app.models.research_context import ResearchBrief

# Well-known disambiguations — prevents confusing RAG with unrelated meanings
_DOMAIN_PATTERNS: list[tuple[re.Pattern[str], ResearchBrief]] = [
    (
        re.compile(r"\brag\b", re.I),
        ResearchBrief(
            normalized_topic="Retrieval-Augmented Generation (RAG) in deep learning",
            disambiguation=(
                "RAG in ML/NLP means Retrieval-Augmented Generation (Lewis et al., NeurIPS 2020): "
                "a system that retrieves relevant documents/passages and conditions a generator "
                "(e.g. LLM) on them. It is NOT 'red-amber-green', random access memory, or generic "
                "'retrieval' alone. Core pieces: retriever (dense/sparse), index, and generator."
            ),
            domain="machine_learning",
            search_queries=[
                "retrieval augmented generation Lewis 2020 NeurIPS",
                "RAG architecture dense retriever large language model",
                "RAG vs fine-tuning LLM knowledge grounding",
                "retrieval augmented generation deep learning survey",
            ],
            key_concepts=[
                "retriever",
                "generator",
                "dense passage retrieval",
                "knowledge grounding",
                "Lewis et al. 2020",
            ],
            must_cover=[
                "Formal definition of RAG in deep learning",
                "How retriever and generator interact",
                "Comparison to fine-tuning and vanilla prompting",
                "Typical applications (QA, chatbots, enterprise search)",
            ],
        ),
    ),
    (
        re.compile(r"\bllm\b|\blarge language model", re.I),
        ResearchBrief(
            normalized_topic="Large Language Models",
            domain="machine_learning",
            search_queries=[
                "large language model architecture transformer",
                "LLM training pretraining fine-tuning RLHF",
            ],
            key_concepts=["transformer", "pretraining", "fine-tuning", "context window"],
        ),
    ),
    (
        re.compile(r"\btransformer\b", re.I),
        ResearchBrief(
            normalized_topic="Transformer neural networks",
            domain="machine_learning",
            search_queries=[
                "transformer architecture attention Vaswani 2017",
                "transformer encoder decoder deep learning",
            ],
            key_concepts=["self-attention", "encoder-decoder", "positional encoding"],
        ),
    ),
]


def heuristic_brief(user_query: str) -> ResearchBrief | None:
    for pattern, brief in _DOMAIN_PATTERNS:
        if pattern.search(user_query):
            brief = brief.model_copy()
            brief.search_queries = [
                f"{q} {user_query[:80]}".strip() for q in brief.search_queries[:4]
            ]
            return brief
    return None


def merge_briefs(
    heuristic: ResearchBrief | None,
    llm_brief: ResearchBrief | None,
    user_query: str,
) -> ResearchBrief:
    if heuristic and llm_brief:
        queries = list(dict.fromkeys(heuristic.search_queries + llm_brief.search_queries))[:6]
        concepts = list(dict.fromkeys(heuristic.key_concepts + llm_brief.key_concepts))
        must = list(dict.fromkeys(heuristic.must_cover + llm_brief.must_cover))
        return ResearchBrief(
            normalized_topic=llm_brief.normalized_topic or heuristic.normalized_topic,
            disambiguation=heuristic.disambiguation or llm_brief.disambiguation,
            domain=heuristic.domain or llm_brief.domain,
            search_queries=queries,
            key_concepts=concepts,
            must_cover=must,
        )
    if heuristic:
        return heuristic
    if llm_brief:
        return llm_brief
    return default_brief(user_query)


def default_brief(user_query: str) -> ResearchBrief:
    return ResearchBrief(
        normalized_topic=user_query,
        search_queries=[user_query, f"{user_query} explained", f"{user_query} overview"],
    )
