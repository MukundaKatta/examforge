"""Short-answer question generator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from examforge.generator.bloom import BloomTaxonomy
from examforge.models import (
    BloomLevel,
    Difficulty,
    Question,
    QuestionType,
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert exam question writer. Generate concise short-answer questions "
    "that test factual recall, conceptual understanding, or the ability to apply knowledge. "
    "Each question should have a clear, definitive answer and a set of grading keywords."
)


def _build_short_answer_prompt(
    topic: str,
    count: int,
    difficulty: Difficulty,
    bloom_level: BloomLevel | None,
    context: str | None,
) -> str:
    bloom_instruction = ""
    if bloom_level:
        bloom_instruction = (
            f' Target Bloom\'s taxonomy level: "{bloom_level.value}". '
            f"Use appropriate action verbs."
        )

    context_block = ""
    if context:
        context_block = f"\n\nSource material:\n{context}\n"

    return (
        f"Generate {count} short-answer question(s) on the topic: \"{topic}\".\n"
        f"Difficulty: {difficulty.value}.{bloom_instruction}{context_block}\n\n"
        "Return ONLY a JSON array. Each element must have:\n"
        '  "question": string,\n'
        '  "answer": string (model answer),\n'
        '  "keywords": [string] (key terms expected in a correct answer)\n'
    )


def _parse_llm_response(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


class ShortAnswerGenerator:
    """Generate short-answer questions using an LLM backend.

    If no ``client`` is provided, questions can still be built manually via
    :meth:`build_question`.
    """

    def __init__(self, client: Any | None = None, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    def generate(
        self,
        topic: str,
        count: int = 5,
        difficulty: Difficulty = Difficulty.MEDIUM,
        bloom_level: BloomLevel | None = None,
        context: str | None = None,
    ) -> list[Question]:
        """Generate short-answer questions via the configured LLM.

        Raises:
            RuntimeError: If no LLM client has been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "No OpenAI client configured. Pass an openai.OpenAI instance to ShortAnswerGenerator."
            )

        prompt = _build_short_answer_prompt(topic, count, difficulty, bloom_level, context)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        raw_text = response.choices[0].message.content or "[]"
        raw_questions = _parse_llm_response(raw_text)

        questions: list[Question] = []
        for rq in raw_questions:
            q = self._raw_to_question(rq, topic, difficulty)
            BloomTaxonomy.classify_and_tag(q)
            questions.append(q)
        return questions

    @staticmethod
    def build_question(
        text: str,
        correct_answer: str,
        keywords: list[str] | None = None,
        topic: str = "",
        difficulty: Difficulty = Difficulty.MEDIUM,
        points: float = 2.0,
    ) -> Question:
        """Build a short-answer question from explicit data."""
        q = Question(
            id=f"sa-{uuid.uuid4().hex[:8]}",
            type=QuestionType.SHORT_ANSWER,
            text=text,
            difficulty=difficulty,
            points=points,
            topic=topic,
            correct_answer=correct_answer,
            keywords=keywords or [],
        )
        BloomTaxonomy.classify_and_tag(q)
        return q

    @staticmethod
    def _raw_to_question(
        raw: dict[str, Any],
        topic: str,
        difficulty: Difficulty,
    ) -> Question:
        return Question(
            id=f"sa-{uuid.uuid4().hex[:8]}",
            type=QuestionType.SHORT_ANSWER,
            text=raw.get("question", ""),
            difficulty=difficulty,
            points=2.0,
            topic=topic,
            correct_answer=raw.get("answer", ""),
            keywords=raw.get("keywords", []),
        )
