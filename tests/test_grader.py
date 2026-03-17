"""Tests for auto-grader and essay grader."""

from __future__ import annotations

import pytest

from examforge.generator.essay import EssayGenerator
from examforge.generator.mcq import MCQGenerator
from examforge.generator.short_answer import ShortAnswerGenerator
from examforge.grader.auto_grader import AutoGrader
from examforge.grader.essay_grader import EssayGrader
from examforge.grader.rubric import Rubric
from examforge.models import (
    Answer,
    Difficulty,
    Exam,
    ExamSubmission,
    GradeReport,
    QuestionType,
)


def _make_exam() -> Exam:
    """Build a small exam with one MCQ, one short-answer, and one essay."""
    mcq = MCQGenerator.build_question(
        text="What is the capital of France?",
        options=[
            {"label": "A", "text": "Berlin", "is_correct": False},
            {"label": "B", "text": "Paris", "is_correct": True},
            {"label": "C", "text": "Madrid", "is_correct": False},
            {"label": "D", "text": "Rome", "is_correct": False},
        ],
        topic="Geography",
        points=1.0,
    )

    sa = ShortAnswerGenerator.build_question(
        text="Define photosynthesis.",
        correct_answer="The process by which plants convert light energy into chemical energy.",
        keywords=["plants", "light", "energy", "chemical"],
        topic="Biology",
        points=4.0,
    )

    essay = EssayGenerator.build_question(
        text="Evaluate the role of technology in modern education.",
        sample_answer="Technology has transformed education...",
        topic="Education",
        points=20.0,
    )
    # Add keywords for fallback grading.
    essay.keywords = ["technology", "education", "learning", "digital", "access"]

    return Exam(
        id="test-exam-001",
        title="Sample Exam",
        questions=[mcq, sa, essay],
    )


# ── AutoGrader (MCQ + Short-Answer) ────────────────────────────


class TestAutoGrader:
    def test_correct_mcq(self):
        exam = _make_exam()
        mcq_id = exam.questions[0].id
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="student-1",
            answers=[Answer(question_id=mcq_id, response="B", selected_option="B")],
        )
        grader = AutoGrader()
        report = grader.grade(exam, sub)
        mcq_result = next(r for r in report.results if r.question_id == mcq_id)
        assert mcq_result.is_correct is True
        assert mcq_result.points_earned == 1.0

    def test_incorrect_mcq(self):
        exam = _make_exam()
        mcq_id = exam.questions[0].id
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="student-2",
            answers=[Answer(question_id=mcq_id, response="A", selected_option="A")],
        )
        grader = AutoGrader()
        report = grader.grade(exam, sub)
        mcq_result = next(r for r in report.results if r.question_id == mcq_id)
        assert mcq_result.is_correct is False
        assert mcq_result.points_earned == 0.0

    def test_unanswered_mcq(self):
        exam = _make_exam()
        mcq_id = exam.questions[0].id
        sub = ExamSubmission(exam_id=exam.id, student_id="student-3", answers=[])
        grader = AutoGrader()
        report = grader.grade(exam, sub)
        mcq_result = next(r for r in report.results if r.question_id == mcq_id)
        assert mcq_result.is_correct is False
        assert mcq_result.feedback == "No answer provided."

    def test_short_answer_full_credit(self):
        exam = _make_exam()
        sa_id = exam.questions[1].id
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="student-4",
            answers=[
                Answer(
                    question_id=sa_id,
                    response="Plants use light energy to produce chemical energy.",
                )
            ],
        )
        grader = AutoGrader()
        report = grader.grade(exam, sub)
        sa_result = next(r for r in report.results if r.question_id == sa_id)
        assert sa_result.is_correct is True
        assert sa_result.points_earned == 4.0

    def test_short_answer_partial_credit(self):
        exam = _make_exam()
        sa_id = exam.questions[1].id
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="student-5",
            answers=[
                Answer(question_id=sa_id, response="Plants convert light.")
            ],
        )
        grader = AutoGrader(keyword_partial_credit=True)
        report = grader.grade(exam, sub)
        sa_result = next(r for r in report.results if r.question_id == sa_id)
        # "plants" and "light" match (2/4 keywords).
        assert sa_result.points_earned == 2.0
        assert sa_result.is_correct is False

    def test_short_answer_no_partial_credit(self):
        exam = _make_exam()
        sa_id = exam.questions[1].id
        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="student-6",
            answers=[
                Answer(question_id=sa_id, response="Plants convert light.")
            ],
        )
        grader = AutoGrader(keyword_partial_credit=False)
        report = grader.grade(exam, sub)
        sa_result = next(r for r in report.results if r.question_id == sa_id)
        assert sa_result.points_earned == 0.0

    def test_essays_are_skipped_by_auto_grader(self):
        exam = _make_exam()
        sub = ExamSubmission(exam_id=exam.id, student_id="student-7", answers=[])
        grader = AutoGrader()
        report = grader.grade(exam, sub)
        # Only MCQ and short-answer results; essay is skipped.
        result_ids = {r.question_id for r in report.results}
        essay_id = exam.questions[2].id
        assert essay_id not in result_ids


# ── EssayGrader (keyword fallback) ─────────────────────────────


class TestEssayGrader:
    def test_keyword_grading_full(self):
        exam = _make_exam()
        essay = exam.questions[2]
        answer = Answer(
            question_id=essay.id,
            response=(
                "Technology has revolutionized education, improving digital access "
                "and transforming the learning experience for millions."
            ),
        )
        result = EssayGrader.grade_by_keywords(essay, answer)
        assert result.points_earned == result.points_possible  # all keywords present

    def test_keyword_grading_partial(self):
        exam = _make_exam()
        essay = exam.questions[2]
        answer = Answer(
            question_id=essay.id,
            response="Technology has changed education significantly.",
        )
        result = EssayGrader.grade_by_keywords(essay, answer)
        # "technology" and "education" match (2/5).
        assert 0 < result.points_earned < result.points_possible

    def test_keyword_grading_none(self):
        exam = _make_exam()
        essay = exam.questions[2]
        answer = Answer(
            question_id=essay.id,
            response="No relevant content here at all.",
        )
        result = EssayGrader.grade_by_keywords(essay, answer)
        assert result.points_earned == 0.0

    def test_essay_grader_rejects_non_essay(self):
        exam = _make_exam()
        mcq = exam.questions[0]
        answer = Answer(question_id=mcq.id, response="A")
        with pytest.raises(ValueError, match="Expected an essay question"):
            EssayGrader.grade_by_keywords(mcq, answer)

    def test_llm_grade_without_client_raises(self):
        exam = _make_exam()
        essay = exam.questions[2]
        answer = Answer(question_id=essay.id, response="Some text.")
        grader = EssayGrader(client=None)
        with pytest.raises(RuntimeError, match="No OpenAI client configured"):
            grader.grade(essay, answer)


# ── Rubric Builder ──────────────────────────────────────────────


class TestRubric:
    def test_builder_chain(self):
        rubric = (
            Rubric("Test")
            .add_criterion("A", 5.0, "First")
            .add_criterion("B", 3.0, "Second")
            .build()
        )
        assert rubric.name == "Test"
        assert len(rubric.criteria) == 2
        assert rubric.max_total == 8.0

    def test_from_model_roundtrip(self):
        from examforge.generator.essay import DEFAULT_ESSAY_RUBRIC

        builder = Rubric.from_model(DEFAULT_ESSAY_RUBRIC)
        rebuilt = builder.build()
        assert rebuilt.name == DEFAULT_ESSAY_RUBRIC.name
        assert len(rebuilt.criteria) == len(DEFAULT_ESSAY_RUBRIC.criteria)


# ── GradeReport properties ─────────────────────────────────────


class TestGradeReport:
    def test_letter_grades(self):
        report = GradeReport(exam_id="x", student_id="s", results=[])
        assert report.letter_grade == "F"  # 0%

    def test_full_integration(self):
        """End-to-end: build exam, submit answers, auto-grade, check report."""
        exam = _make_exam()
        mcq_id = exam.questions[0].id
        sa_id = exam.questions[1].id

        sub = ExamSubmission(
            exam_id=exam.id,
            student_id="integration-student",
            answers=[
                Answer(question_id=mcq_id, response="B", selected_option="B"),
                Answer(
                    question_id=sa_id,
                    response="Plants use light energy to produce chemical energy.",
                ),
            ],
        )

        grader = AutoGrader()
        report = grader.grade(exam, sub)

        # MCQ correct (1pt) + SA full (4pt) = 5/5
        assert report.total_earned == 5.0
        assert report.total_possible == 5.0
        assert report.percentage == 100.0
        assert report.letter_grade == "A"
