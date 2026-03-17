"""Multiple-choice question generator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from examforge.generator.bloom import BloomTaxonomy
from examforge.models import (
    BloomLevel,
    Difficulty,
    MCQOption,
    Question,
    QuestionType,
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert exam question writer. Generate high-quality multiple-choice "
    "questions suitable for academic assessment. Each question must have exactly one "
    "correct answer and plausible distractors."
)


def _build_mcq_prompt(
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
            f"Use action verbs appropriate for that cognitive level."
        )

    context_block = ""
    if context:
        context_block = f"\n\nSource material:\n{context}\n"

    return (
        f"Generate {count} multiple-choice question(s) on the topic: \"{topic}\".\n"
        f"Difficulty: {difficulty.value}.{bloom_instruction}{context_block}\n\n"
        "Return ONLY a JSON array. Each element must have:\n"
        '  "question": string,\n'
        '  "options": [{"label": "A", "text": "...", "is_correct": bool}, ...],\n'
        '  "correct_label": string,\n'
        '  "explanation": string\n'
        "Provide exactly 4 options (A-D) per question."
    )


def _parse_llm_mcqs(raw: str) -> list[dict[str, Any]]:
    """Parse the LLM's JSON response into a list of raw MCQ dicts."""
    text = raw.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


class MCQGenerator:
    """Generate multiple-choice questions using an LLM backend.

    If no ``client`` is provided, questions can still be built manually via
    :meth:`build_question`.
    """

    def __init__(self, client: Any | None = None, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    # ------------------------------------------------------------------
    # LLM-backed generation
    # ------------------------------------------------------------------

    def generate(
        self,
        topic: str,
        count: int = 5,
        difficulty: Difficulty = Difficulty.MEDIUM,
        bloom_level: BloomLevel | None = None,
        context: str | None = None,
    ) -> list[Question]:
        """Generate MCQs via the configured LLM.

        Args:
            topic: Subject area for the questions.
            count: Number of questions to generate.
            difficulty: Desired difficulty tier.
            bloom_level: Optional Bloom's level to target.
            context: Optional source material the questions should draw on.

        Returns:
            A list of fully-formed Question objects.

        Raises:
            RuntimeError: If no LLM client has been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "No OpenAI client configured. Pass an openai.OpenAI instance to MCQGenerator."
            )

        prompt = _build_mcq_prompt(topic, count, difficulty, bloom_level, context)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        raw_text = response.choices[0].message.content or "[]"
        raw_questions = _parse_llm_mcqs(raw_text)

        questions: list[Question] = []
        for idx, rq in enumerate(raw_questions, start=1):
            q = self._raw_to_question(rq, topic, difficulty, idx)
            BloomTaxonomy.classify_and_tag(q)
            questions.append(q)

        return questions

    # ------------------------------------------------------------------
    # Manual / programmatic construction
    # ------------------------------------------------------------------

    @staticmethod
    def build_question(
        text: str,
        options: list[dict[str, str | bool]],
        topic: str = "",
        difficulty: Difficulty = Difficulty.MEDIUM,
        points: float = 1.0,
    ) -> Question:
        """Build a single MCQ question from explicit data.

        Args:
            text: The question stem.
            options: List of dicts with keys ``label``, ``text``, ``is_correct``.
            topic: Subject tag.
            difficulty: Difficulty tier.
            points: Point value.

        Returns:
            A tagged Question object.
        """
        mcq_options = [
            MCQOption(
                label=str(o.get("label", "")),
                text=str(o.get("text", "")),
                is_correct=bool(o.get("is_correct", False)),
            )
            for o in options
        ]

        correct = next((o for o in mcq_options if o.is_correct), None)
        correct_answer = correct.text if correct else ""

        q = Question(
            id=f"mcq-{uuid.uuid4().hex[:8]}",
            type=QuestionType.MCQ,
            text=text,
            difficulty=difficulty,
            points=points,
            topic=topic,
            options=mcq_options,
            correct_answer=correct_answer,
        )
        BloomTaxonomy.classify_and_tag(q)
        return q

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_to_question(
        raw: dict[str, Any],
        topic: str,
        difficulty: Difficulty,
        index: int,
    ) -> Question:
        options = [
            MCQOption(
                label=o.get("label", chr(64 + i)),
                text=o.get("text", ""),
                is_correct=bool(o.get("is_correct", False)),
            )
            for i, o in enumerate(raw.get("options", []), start=1)
        ]
        correct = next((o for o in options if o.is_correct), None)

        return Question(
            id=f"mcq-{uuid.uuid4().hex[:8]}",
            type=QuestionType.MCQ,
            text=raw.get("question", f"Question {index}"),
            difficulty=difficulty,
            points=1.0,
            topic=topic,
            options=options,
            correct_answer=correct.text if correct else "",
            metadata={"explanation": raw.get("explanation", "")},
        )
