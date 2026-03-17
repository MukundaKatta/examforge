"""Pydantic data models for ExamForge."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BloomLevel(str, Enum):
    """Bloom's taxonomy cognitive levels, ordered from lowest to highest."""

    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class QuestionType(str, Enum):
    """Supported question types."""

    MCQ = "mcq"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class Difficulty(str, Enum):
    """Question difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MCQOption(BaseModel):
    """A single option in a multiple-choice question."""

    label: str = Field(..., description="Option label, e.g. 'A', 'B', 'C', 'D'")
    text: str = Field(..., description="Option text")
    is_correct: bool = Field(default=False, description="Whether this is the correct answer")


class RubricCriterion(BaseModel):
    """A single criterion within a grading rubric."""

    name: str = Field(..., description="Criterion name, e.g. 'Thesis clarity'")
    description: str = Field(default="", description="What this criterion evaluates")
    max_points: float = Field(..., gt=0, description="Maximum points for this criterion")
    levels: dict[str, str] = Field(
        default_factory=dict,
        description="Scoring level descriptions, e.g. {'excellent': '...', 'good': '...'}",
    )


class RubricModel(BaseModel):
    """A rubric for evaluating essay responses."""

    name: str = Field(default="Default Rubric")
    criteria: list[RubricCriterion] = Field(default_factory=list)

    @property
    def max_total(self) -> float:
        return sum(c.max_points for c in self.criteria)


class Question(BaseModel):
    """A single exam question."""

    id: str = Field(..., description="Unique question identifier")
    type: QuestionType
    text: str = Field(..., description="The question prompt")
    bloom_level: BloomLevel = Field(default=BloomLevel.REMEMBER)
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM)
    points: float = Field(default=1.0, gt=0)
    topic: str = Field(default="")
    options: list[MCQOption] | None = Field(default=None, description="MCQ options (MCQ only)")
    correct_answer: str | None = Field(default=None, description="Correct answer text")
    sample_answer: str | None = Field(default=None, description="Sample/model answer")
    rubric: RubricModel | None = Field(default=None, description="Grading rubric (essay only)")
    keywords: list[str] = Field(default_factory=list, description="Key terms expected in answer")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Exam(BaseModel):
    """A complete exam containing multiple questions."""

    id: str = Field(..., description="Unique exam identifier")
    title: str = Field(default="Untitled Exam")
    description: str = Field(default="")
    topic: str = Field(default="")
    questions: list[Question] = Field(default_factory=list)
    time_limit_minutes: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_points(self) -> float:
        return sum(q.points for q in self.questions)

    @property
    def question_count(self) -> int:
        return len(self.questions)

    def questions_by_type(self, qtype: QuestionType) -> list[Question]:
        return [q for q in self.questions if q.type == qtype]

    def questions_by_bloom(self, level: BloomLevel) -> list[Question]:
        return [q for q in self.questions if q.bloom_level == level]


class Answer(BaseModel):
    """A student's answer to a single question."""

    question_id: str
    response: str = Field(..., description="Student's response text")
    selected_option: str | None = Field(default=None, description="Selected MCQ label")


class ExamSubmission(BaseModel):
    """A student's complete exam submission."""

    exam_id: str
    student_id: str = Field(default="anonymous")
    answers: list[Answer] = Field(default_factory=list)

    def answer_for(self, question_id: str) -> Answer | None:
        for a in self.answers:
            if a.question_id == question_id:
                return a
        return None


class QuestionResult(BaseModel):
    """Grading result for a single question."""

    question_id: str
    points_earned: float = Field(default=0.0, ge=0)
    points_possible: float = Field(default=1.0, gt=0)
    is_correct: bool | None = Field(default=None, description="For MCQ/short answer")
    feedback: str = Field(default="")
    criterion_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-criterion scores for essay grading",
    )

    @property
    def percentage(self) -> float:
        if self.points_possible == 0:
            return 0.0
        return (self.points_earned / self.points_possible) * 100


class GradeReport(BaseModel):
    """Complete grading results for an exam submission."""

    exam_id: str
    student_id: str = Field(default="anonymous")
    results: list[QuestionResult] = Field(default_factory=list)

    @property
    def total_earned(self) -> float:
        return sum(r.points_earned for r in self.results)

    @property
    def total_possible(self) -> float:
        return sum(r.points_possible for r in self.results)

    @property
    def percentage(self) -> float:
        if self.total_possible == 0:
            return 0.0
        return (self.total_earned / self.total_possible) * 100

    @property
    def letter_grade(self) -> str:
        pct = self.percentage
        if pct >= 93:
            return "A"
        if pct >= 90:
            return "A-"
        if pct >= 87:
            return "B+"
        if pct >= 83:
            return "B"
        if pct >= 80:
            return "B-"
        if pct >= 77:
            return "C+"
        if pct >= 73:
            return "C"
        if pct >= 70:
            return "C-"
        if pct >= 67:
            return "D+"
        if pct >= 60:
            return "D"
        return "F"

    def results_by_type(self, exam: Exam) -> dict[QuestionType, list[QuestionResult]]:
        """Group results by question type."""
        q_map = {q.id: q for q in exam.questions}
        grouped: dict[QuestionType, list[QuestionResult]] = {}
        for r in self.results:
            q = q_map.get(r.question_id)
            if q:
                grouped.setdefault(q.type, []).append(r)
        return grouped
