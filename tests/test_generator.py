"""Tests for question generators and Bloom's taxonomy classification."""

from __future__ import annotations

import pytest

from examforge.generator.bloom import BloomTaxonomy
from examforge.generator.essay import DEFAULT_ESSAY_RUBRIC, EssayGenerator
from examforge.generator.mcq import MCQGenerator
from examforge.generator.short_answer import ShortAnswerGenerator
from examforge.models import BloomLevel, Difficulty, Question, QuestionType


# ── Bloom's Taxonomy ────────────────────────────────────────────


class TestBloomTaxonomy:
    def test_remember_verbs(self):
        assert BloomTaxonomy.classify("List the parts of a cell.") == BloomLevel.REMEMBER

    def test_understand_verbs(self):
        assert BloomTaxonomy.classify("Explain the process of photosynthesis.") == BloomLevel.UNDERSTAND

    def test_apply_verbs(self):
        assert BloomTaxonomy.classify("Calculate the velocity of the object.") == BloomLevel.APPLY

    def test_analyze_verbs(self):
        assert BloomTaxonomy.classify("Analyze the causes of World War I.") == BloomLevel.ANALYZE

    def test_evaluate_verbs(self):
        assert BloomTaxonomy.classify("Evaluate the effectiveness of the policy.") == BloomLevel.EVALUATE

    def test_create_verbs(self):
        assert BloomTaxonomy.classify("Design an experiment to test the hypothesis.") == BloomLevel.CREATE

    def test_highest_level_wins(self):
        # "List" is REMEMBER but "evaluate" is EVALUATE -- highest wins.
        result = BloomTaxonomy.classify("List the criteria and evaluate the outcome.")
        assert result == BloomLevel.EVALUATE

    def test_no_verbs_defaults_to_remember(self):
        assert BloomTaxonomy.classify("What is 2 + 2?") == BloomLevel.REMEMBER

    def test_classify_question_object(self):
        q = Question(
            id="q1",
            type=QuestionType.SHORT_ANSWER,
            text="Summarize the key findings of the study.",
        )
        assert BloomTaxonomy.classify(q) == BloomLevel.UNDERSTAND

    def test_classify_and_tag_mutates(self):
        q = Question(
            id="q2",
            type=QuestionType.SHORT_ANSWER,
            text="Analyze the relationship between supply and demand.",
        )
        result = BloomTaxonomy.classify_and_tag(q)
        assert result is q
        assert q.bloom_level == BloomLevel.ANALYZE

    def test_get_verbs(self):
        verbs = BloomTaxonomy.get_verbs(BloomLevel.CREATE)
        assert "design" in verbs
        assert "create" in verbs

    def test_all_levels(self):
        levels = BloomTaxonomy.all_levels()
        assert len(levels) == 6
        assert levels[0] == BloomLevel.REMEMBER
        assert levels[-1] == BloomLevel.CREATE


# ── MCQ Generator ──────────────────────────────────────────────


class TestMCQGenerator:
    def test_build_question_creates_valid_mcq(self):
        q = MCQGenerator.build_question(
            text="What is the powerhouse of the cell?",
            options=[
                {"label": "A", "text": "Nucleus", "is_correct": False},
                {"label": "B", "text": "Mitochondria", "is_correct": True},
                {"label": "C", "text": "Ribosome", "is_correct": False},
                {"label": "D", "text": "Golgi apparatus", "is_correct": False},
            ],
            topic="Biology",
        )
        assert q.type == QuestionType.MCQ
        assert q.correct_answer == "Mitochondria"
        assert len(q.options) == 4
        assert q.topic == "Biology"
        assert q.id.startswith("mcq-")

    def test_build_question_assigns_bloom(self):
        q = MCQGenerator.build_question(
            text="Identify the correct formula for water.",
            options=[
                {"label": "A", "text": "H2O", "is_correct": True},
                {"label": "B", "text": "CO2", "is_correct": False},
                {"label": "C", "text": "NaCl", "is_correct": False},
                {"label": "D", "text": "O2", "is_correct": False},
            ],
        )
        assert q.bloom_level == BloomLevel.REMEMBER

    def test_generate_without_client_raises(self):
        gen = MCQGenerator(client=None)
        with pytest.raises(RuntimeError, match="No OpenAI client configured"):
            gen.generate(topic="Math", count=1)

    def test_build_question_with_difficulty(self):
        q = MCQGenerator.build_question(
            text="Solve for x: 2x + 3 = 7",
            options=[
                {"label": "A", "text": "1", "is_correct": False},
                {"label": "B", "text": "2", "is_correct": True},
                {"label": "C", "text": "3", "is_correct": False},
                {"label": "D", "text": "4", "is_correct": False},
            ],
            difficulty=Difficulty.EASY,
            points=2.0,
        )
        assert q.difficulty == Difficulty.EASY
        assert q.points == 2.0


# ── Short-Answer Generator ─────────────────────────────────────


class TestShortAnswerGenerator:
    def test_build_question(self):
        q = ShortAnswerGenerator.build_question(
            text="Explain the role of mitochondria in cellular respiration.",
            correct_answer="Mitochondria produce ATP through oxidative phosphorylation.",
            keywords=["ATP", "oxidative phosphorylation", "energy"],
            topic="Biology",
        )
        assert q.type == QuestionType.SHORT_ANSWER
        assert q.bloom_level == BloomLevel.UNDERSTAND  # "Explain"
        assert "ATP" in q.keywords

    def test_generate_without_client_raises(self):
        gen = ShortAnswerGenerator(client=None)
        with pytest.raises(RuntimeError, match="No OpenAI client configured"):
            gen.generate(topic="History", count=1)


# ── Essay Generator ─────────────────────────────────────────────


class TestEssayGenerator:
    def test_build_question_with_default_rubric(self):
        q = EssayGenerator.build_question(
            text="Evaluate the impact of the Industrial Revolution on modern society.",
            topic="History",
        )
        assert q.type == QuestionType.ESSAY
        assert q.rubric is not None
        assert q.rubric.name == "Standard Essay Rubric"
        assert len(q.rubric.criteria) == 5
        assert q.bloom_level == BloomLevel.EVALUATE

    def test_build_question_with_custom_rubric(self):
        from examforge.grader.rubric import Rubric

        rubric = (
            Rubric("Custom")
            .add_criterion("Accuracy", 10.0, "Factual correctness")
            .add_criterion("Clarity", 5.0, "Writing quality")
            .build()
        )
        q = EssayGenerator.build_question(
            text="Discuss the causes of climate change.",
            rubric=rubric,
            points=15.0,
        )
        assert q.rubric.name == "Custom"
        assert len(q.rubric.criteria) == 2
        assert q.rubric.max_total == 15.0

    def test_default_rubric_max_total(self):
        assert DEFAULT_ESSAY_RUBRIC.max_total == 20.0

    def test_generate_without_client_raises(self):
        gen = EssayGenerator(client=None)
        with pytest.raises(RuntimeError, match="No OpenAI client configured"):
            gen.generate(topic="Philosophy", count=1)
