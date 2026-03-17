"""Essay prompt generator with rubric creation."""

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
    RubricCriterion,
    RubricModel,
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert exam designer. Generate thought-provoking essay prompts "
    "with detailed grading rubrics. Each rubric should have 3-5 criteria with "
    "clear scoring-level descriptions."
)

# Standard rubric template used when building questions manually.
DEFAULT_ESSAY_RUBRIC = RubricModel(
    name="Standard Essay Rubric",
    criteria=[
        RubricCriterion(
            name="Thesis & Argument",
            description="Clarity and strength of the central thesis.",
            max_points=5.0,
            levels={
                "excellent": "Clear, compelling thesis with nuanced argumentation.",
                "good": "Solid thesis with adequate supporting arguments.",
                "adequate": "Thesis present but underdeveloped.",
                "poor": "No discernible thesis or coherent argument.",
            },
        ),
        RubricCriterion(
            name="Evidence & Support",
            description="Use of relevant evidence, examples, and citations.",
            max_points=5.0,
            levels={
                "excellent": "Rich, well-integrated evidence from multiple sources.",
                "good": "Sufficient evidence with some integration.",
                "adequate": "Limited evidence; loosely connected to claims.",
                "poor": "No meaningful evidence provided.",
            },
        ),
        RubricCriterion(
            name="Analysis & Critical Thinking",
            description="Depth of analysis and demonstration of higher-order thinking.",
            max_points=5.0,
            levels={
                "excellent": "Insightful analysis; addresses counter-arguments.",
                "good": "Competent analysis with some depth.",
                "adequate": "Superficial analysis; mostly descriptive.",
                "poor": "No analysis; merely restates facts.",
            },
        ),
        RubricCriterion(
            name="Organization & Coherence",
            description="Logical structure, transitions, and readability.",
            max_points=3.0,
            levels={
                "excellent": "Seamless organization with effective transitions.",
                "good": "Generally well-organized; minor lapses.",
                "adequate": "Some organizational issues affecting clarity.",
                "poor": "Disorganized; difficult to follow.",
            },
        ),
        RubricCriterion(
            name="Language & Mechanics",
            description="Grammar, vocabulary, and academic tone.",
            max_points=2.0,
            levels={
                "excellent": "Polished prose; virtually error-free.",
                "good": "Minor errors that do not impede understanding.",
                "adequate": "Noticeable errors; inconsistent tone.",
                "poor": "Frequent errors; informal or unclear writing.",
            },
        ),
    ],
)


def _build_essay_prompt(
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
            f"Frame the prompt to elicit that cognitive level."
        )

    context_block = ""
    if context:
        context_block = f"\n\nSource material:\n{context}\n"

    return (
        f"Generate {count} essay prompt(s) on the topic: \"{topic}\".\n"
        f"Difficulty: {difficulty.value}.{bloom_instruction}{context_block}\n\n"
        "Return ONLY a JSON array. Each element must have:\n"
        '  "prompt": string (the essay question),\n'
        '  "sample_answer": string (a brief model response outline),\n'
        '  "rubric": [\n'
        '    {"name": string, "description": string, "max_points": number,\n'
        '     "levels": {"excellent": "...", "good": "...", "adequate": "...", "poor": "..."}}\n'
        "  ]\n"
    )


def _parse_llm_response(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


class EssayGenerator:
    """Generate essay prompts with grading rubrics.

    If no ``client`` is provided, questions can be built manually via
    :meth:`build_question`, which attaches the default rubric.
    """

    def __init__(self, client: Any | None = None, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    def generate(
        self,
        topic: str,
        count: int = 2,
        difficulty: Difficulty = Difficulty.MEDIUM,
        bloom_level: BloomLevel | None = None,
        context: str | None = None,
    ) -> list[Question]:
        """Generate essay prompts via the configured LLM.

        Raises:
            RuntimeError: If no LLM client has been configured.
        """
        if self._client is None:
            raise RuntimeError(
                "No OpenAI client configured. Pass an openai.OpenAI instance to EssayGenerator."
            )

        prompt = _build_essay_prompt(topic, count, difficulty, bloom_level, context)
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
        sample_answer: str = "",
        rubric: RubricModel | None = None,
        topic: str = "",
        difficulty: Difficulty = Difficulty.MEDIUM,
        points: float = 20.0,
    ) -> Question:
        """Build an essay question from explicit data.

        Uses the default rubric if none is provided.
        """
        effective_rubric = rubric or DEFAULT_ESSAY_RUBRIC
        q = Question(
            id=f"essay-{uuid.uuid4().hex[:8]}",
            type=QuestionType.ESSAY,
            text=text,
            difficulty=difficulty,
            points=points,
            topic=topic,
            sample_answer=sample_answer,
            rubric=effective_rubric,
        )
        BloomTaxonomy.classify_and_tag(q)
        return q

    @staticmethod
    def _raw_to_question(
        raw: dict[str, Any],
        topic: str,
        difficulty: Difficulty,
    ) -> Question:
        rubric_data = raw.get("rubric", [])
        criteria = [
            RubricCriterion(
                name=c.get("name", "Criterion"),
                description=c.get("description", ""),
                max_points=float(c.get("max_points", 5)),
                levels=c.get("levels", {}),
            )
            for c in rubric_data
        ]
        rubric = RubricModel(name="Generated Rubric", criteria=criteria) if criteria else DEFAULT_ESSAY_RUBRIC

        return Question(
            id=f"essay-{uuid.uuid4().hex[:8]}",
            type=QuestionType.ESSAY,
            text=raw.get("prompt", ""),
            difficulty=difficulty,
            points=rubric.max_total,
            topic=topic,
            sample_answer=raw.get("sample_answer", ""),
            rubric=rubric,
        )
