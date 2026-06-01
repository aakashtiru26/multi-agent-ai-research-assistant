from pydantic import BaseModel, Field


class ResearchBrief(BaseModel):
    """Query understanding output (Perplexity / GPT-Researcher style)."""

    normalized_topic: str = ""
    disambiguation: str = ""
    domain: str = "general"
    search_queries: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        lines = [
            f"TOPIC: {self.normalized_topic}",
            f"DOMAIN: {self.domain}",
        ]
        if self.disambiguation:
            lines.append(f"DISAMBIGUATION (follow this): {self.disambiguation}")
        if self.key_concepts:
            lines.append("KEY CONCEPTS: " + ", ".join(self.key_concepts))
        if self.must_cover:
            lines.append("MUST COVER: " + "; ".join(self.must_cover))
        return "\n".join(lines)
