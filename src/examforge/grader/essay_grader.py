"""LLM-based essay grader using rubric criteria."""

from __future__ import annotations

import json
from typing import Any

from examforge.models import (
    Answer,
    Question,
    QuestionResult,
    QuestionType,
    RubricModel,
)

_SYSTEM_PROMPT = (
    "You are an expert academic essay grader. Evaluate the student's essay "
    "against each rubric criterion. Be fair, specific, and constructive."
)


def _build_grading_prompt(question: Question, response_text: str) -> str:
    rubric = question.rubric
    if rubric is None:
        raise ValueError("Essay question has no rubric attached.")

    criteria_block = "\n".join(
        f"  - {c.name} (max {c.max_points} pts): {c.description}"
        for c in rubric.criteria
    )

    sample = ""
    if question.sample_answer:
        sample = f"\nModel answer outline:\n{question.sample_answer}\n"

    return (
        f"Essay prompt:\n{question.text}\n{sample}"
        f"\nGrading rubric:\n{criteria_block}\n\n"
        f"Student response:\n{response_text}\n\n"
        "Grade the essay. Return ONLY a JSON object with:\n"
        '  "scores": {{"<criterion_name>": <points_earned>, ...}},\n'
        '  "feedback": "<overall feedback string>"\n'
        "Each score must be between 0 and the criterion's max_points."
    )


def _parse_grading_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


class EssayGrader:
    """Grade essay responses against a rubric using an LLM.

    Also supports a deterministic :meth:`grade_by_keywords` fallback when
    no LLM client is available.
    """

    def __init__(self, client: Any | None = None, model: str = "gpt-4o") -> None:
        self._client = client
        self._model = model

    def grade(self, question: Question, answer: Answer) -> QuestionResult:
        """Grade a single essay answer via the configured LLM.

        Raises:
            RuntimeError: If no LLM client has been configured.
            ValueError: If the question has no rubric.
        """
        if question.type != QuestionType.ESSAY:
            raise ValueError(f"Expected an essay question, got {question.type.value}.")
        if self._client is None:
            raise RuntimeError(
                "No OpenAI client configured. Pass an openai.OpenAI instance to EssayGrader."
            )

        prompt = _build_grading_prompt(question, answer.response)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        raw_text = response.choices[0].message.content or "{}"
        parsed = _parse_grading_response(raw_text)

        scores: dict[str, float] = parsed.get("scores", {})
        feedback: str = parsed.get("feedback", "")

        # Clamp each score to the criterion's max.
        rubric = question.rubric
        if rubric:
            for criterion in rubric.criteria:
                if criterion.name in scores:
                    scores[criterion.name] = min(
                        max(float(scores[criterion.name]), 0),
                        criterion.max_points,
                    )

        total_earned = sum(scores.values())
        total_possible = rubric.max_total if rubric else question.points

        return QuestionResult(
            question_id=question.id,
            points_earned=round(total_earned, 2),
            points_possible=total_possible,
            feedback=feedback,
            criterion_scores=scores,
        )

    @staticmethod
    def grade_by_keywords(question: Question, answer: Answer) -> QuestionResult:
        """Deterministic keyword-overlap grading fallback (no LLM needed).

        Awards partial credit based on the fraction of expected keywords
        found in the student's response.
        """
        if question.type != QuestionType.ESSAY:
            raise ValueError(f"Expected an essay question, got {question.type.value}.")

        rubric: RubricModel | None = question.rubric
        total_possible = rubric.max_total if rubric else question.points
        keywords = question.keywords

        if not keywords:
            return QuestionResult(
                question_id=question.id,
                points_earned=0.0,
                points_possible=total_possible,
                feedback="No keywords defined for automated grading.",
            )

        response_lower = answer.response.lower()
        matched = [kw for kw in keywords if kw.lower() in response_lower]
        ratio = len(matched) / len(keywords)
        earned = round(total_possible * ratio, 2)

        missing = set(keywords) - {kw for kw in keywords if kw.lower() in response_lower}
        feedback = f"Keyword match: {len(matched)}/{len(keywords)}."
        if missing:
            feedback += f" Missing: {', '.join(sorted(missing))}."

        return QuestionResult(
            question_id=question.id,
            points_earned=earned,
            points_possible=total_possible,
            feedback=feedback,
        )
