"""Content parser for extracting key concepts from text."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


class ExtractedConcept(BaseModel):
    """A single concept extracted from source material."""

    term: str = Field(..., description="Key term or concept name")
    definition: str = Field(default="", description="Brief definition or explanation")
    importance: str = Field(default="medium", description="low / medium / high")


class ParsedContent(BaseModel):
    """Result of parsing source material."""

    title: str = Field(default="Untitled")
    raw_text: str = Field(default="")
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    summary: str = Field(default="")
    word_count: int = Field(default=0)

    @property
    def concept_terms(self) -> list[str]:
        return [c.term for c in self.concepts]


class ContentParser:
    """Extract key concepts and structure from source text.

    Supports plain-text input directly. LLM-assisted extraction is available
    when an OpenAI client is provided; otherwise a simple heuristic extractor
    is used.
    """

    def __init__(self, client: Any | None = None, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    def parse(self, text: str, title: str = "Untitled") -> ParsedContent:
        """Parse raw text and extract key concepts.

        Uses the LLM if available, otherwise falls back to heuristic extraction.
        """
        word_count = len(text.split())
        if self._client is not None:
            return self._parse_with_llm(text, title, word_count)
        return self._parse_heuristic(text, title, word_count)

    # ------------------------------------------------------------------
    # LLM-assisted parsing
    # ------------------------------------------------------------------

    def _parse_with_llm(self, text: str, title: str, word_count: int) -> ParsedContent:
        prompt = (
            "Analyze the following text and extract key concepts.\n\n"
            f"Text:\n{text[:8000]}\n\n"
            "Return a JSON object with:\n"
            '  "summary": "<brief summary>",\n'
            '  "concepts": [\n'
            '    {"term": "...", "definition": "...", "importance": "low|medium|high"}\n'
            "  ]\n"
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
        data = json.loads(raw)

        concepts = [
            ExtractedConcept(
                term=c.get("term", ""),
                definition=c.get("definition", ""),
                importance=c.get("importance", "medium"),
            )
            for c in data.get("concepts", [])
        ]

        return ParsedContent(
            title=title,
            raw_text=text,
            concepts=concepts,
            summary=data.get("summary", ""),
            word_count=word_count,
        )

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_heuristic(text: str, title: str, word_count: int) -> ParsedContent:
        """Simple keyword-frequency extraction without an LLM."""
        # Tokenize and count word frequencies (excluding stop words).
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "must", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
            "during", "before", "after", "above", "below", "between", "out", "off",
            "over", "under", "again", "further", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "each", "every", "both", "few",
            "more", "most", "other", "some", "such", "no", "not", "only", "own",
            "same", "so", "than", "too", "very", "and", "but", "or", "nor", "if",
            "that", "this", "these", "those", "it", "its", "they", "them", "their",
            "he", "she", "we", "you", "i", "me", "my", "your", "his", "her", "our",
            "what", "which", "who", "whom", "about", "also", "just", "because",
        }

        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if w not in stop_words:
                freq[w] = freq.get(w, 0) + 1

        top_terms = sorted(freq, key=freq.get, reverse=True)[:15]  # type: ignore[arg-type]
        concepts = [
            ExtractedConcept(term=t, importance="high" if freq[t] > 3 else "medium")
            for t in top_terms
        ]

        sentences = re.split(r"[.!?]+", text)
        summary = ". ".join(s.strip() for s in sentences[:3] if s.strip()) + "."

        return ParsedContent(
            title=title,
            raw_text=text,
            concepts=concepts,
            summary=summary,
            word_count=word_count,
        )
