"""Automatic grader for MCQ and short-answer questions."""

from __future__ import annotations

from examforge.models import (
    Answer,
    Exam,
    ExamSubmission,
    GradeReport,
    Question,
    QuestionResult,
    QuestionType,
)


def _normalize(text: str) -> str:
    """Lowercase, strip, and collapse whitespace for fuzzy comparison."""
    return " ".join(text.lower().split())


class AutoGrader:
    """Grade MCQ and short-answer questions automatically.

    MCQs are graded by exact option-label match. Short-answer questions are
    graded by keyword overlap against the expected keywords list.
    """

    def __init__(self, keyword_partial_credit: bool = True) -> None:
        """
        Args:
            keyword_partial_credit: When True, short-answer grading awards
                partial credit proportional to keyword matches. When False,
                all keywords must appear for full credit (else zero).
        """
        self._keyword_partial = keyword_partial_credit

    def grade(self, exam: Exam, submission: ExamSubmission) -> GradeReport:
        """Grade an entire submission against the exam.

        Only MCQ and SHORT_ANSWER questions are graded. Essay questions are
        skipped (use :class:`EssayGrader` for those).
        """
        results: list[QuestionResult] = []
        for question in exam.questions:
            answer = submission.answer_for(question.id)
            if question.type == QuestionType.MCQ:
                results.append(self._grade_mcq(question, answer))
            elif question.type == QuestionType.SHORT_ANSWER:
                results.append(self._grade_short_answer(question, answer))
            # Essays are intentionally skipped.

        return GradeReport(
            exam_id=exam.id,
            student_id=submission.student_id,
            results=results,
        )

    # ------------------------------------------------------------------
    # MCQ grading
    # ------------------------------------------------------------------

    @staticmethod
    def _grade_mcq(question: Question, answer: Answer | None) -> QuestionResult:
        if answer is None:
            return QuestionResult(
                question_id=question.id,
                points_earned=0.0,
                points_possible=question.points,
                is_correct=False,
                feedback="No answer provided.",
            )

        # Determine the correct label from the options list.
        correct_label: str | None = None
        if question.options:
            for opt in question.options:
                if opt.is_correct:
                    correct_label = opt.label
                    break

        selected = (answer.selected_option or answer.response).strip().upper()
        is_correct = selected == (correct_label or "").upper()

        return QuestionResult(
            question_id=question.id,
            points_earned=question.points if is_correct else 0.0,
            points_possible=question.points,
            is_correct=is_correct,
            feedback="Correct!" if is_correct else f"Incorrect. The correct answer is {correct_label}.",
        )

    # ------------------------------------------------------------------
    # Short-answer grading
    # ------------------------------------------------------------------

    def _grade_short_answer(self, question: Question, answer: Answer | None) -> QuestionResult:
        if answer is None:
            return QuestionResult(
                question_id=question.id,
                points_earned=0.0,
                points_possible=question.points,
                is_correct=False,
                feedback="No answer provided.",
            )

        if not question.keywords:
            # Fall back to exact-match against the correct_answer field.
            is_match = _normalize(answer.response) == _normalize(question.correct_answer or "")
            return QuestionResult(
                question_id=question.id,
                points_earned=question.points if is_match else 0.0,
                points_possible=question.points,
                is_correct=is_match,
                feedback="Correct!" if is_match else "Incorrect.",
            )

        response_norm = _normalize(answer.response)
        matched = [kw for kw in question.keywords if kw.lower() in response_norm]
        match_ratio = len(matched) / len(question.keywords)

        if self._keyword_partial:
            earned = round(question.points * match_ratio, 2)
        else:
            earned = question.points if match_ratio == 1.0 else 0.0

        is_correct = match_ratio == 1.0
        missing = [kw for kw in question.keywords if kw.lower() not in response_norm]
        feedback_parts = [f"Matched {len(matched)}/{len(question.keywords)} keywords."]
        if missing:
            feedback_parts.append(f"Missing: {', '.join(missing)}.")

        return QuestionResult(
            question_id=question.id,
            points_earned=earned,
            points_possible=question.points,
            is_correct=is_correct,
            feedback=" ".join(feedback_parts),
        )
