#!/usr/bin/env python3
"""Example: programmatically build an exam, grade it, and display a report.

This example works without an OpenAI key -- it uses the manual builder
methods and the keyword-based grading fallback.
"""

from rich.console import Console

from examforge.generator.bloom import BloomTaxonomy
from examforge.generator.essay import EssayGenerator
from examforge.generator.mcq import MCQGenerator
from examforge.generator.short_answer import ShortAnswerGenerator
from examforge.grader.auto_grader import AutoGrader
from examforge.grader.essay_grader import EssayGrader
from examforge.grader.rubric import Rubric
from examforge.models import Answer, Exam, ExamSubmission
from examforge.report import render_grade_report


def main() -> None:
    console = Console()

    # ── 1. Build questions manually ─────────────────────────────
    console.print("[bold blue]Building exam...[/bold blue]\n")

    mcq1 = MCQGenerator.build_question(
        text="Identify the organelle responsible for ATP production.",
        options=[
            {"label": "A", "text": "Nucleus", "is_correct": False},
            {"label": "B", "text": "Mitochondria", "is_correct": True},
            {"label": "C", "text": "Endoplasmic reticulum", "is_correct": False},
            {"label": "D", "text": "Golgi apparatus", "is_correct": False},
        ],
        topic="Cell Biology",
        points=1.0,
    )

    mcq2 = MCQGenerator.build_question(
        text="Which molecule carries genetic information?",
        options=[
            {"label": "A", "text": "RNA", "is_correct": False},
            {"label": "B", "text": "ATP", "is_correct": False},
            {"label": "C", "text": "DNA", "is_correct": True},
            {"label": "D", "text": "Protein", "is_correct": False},
        ],
        topic="Cell Biology",
        points=1.0,
    )

    sa1 = ShortAnswerGenerator.build_question(
        text="Explain the difference between prokaryotic and eukaryotic cells.",
        correct_answer="Eukaryotic cells have a membrane-bound nucleus; prokaryotic cells do not.",
        keywords=["nucleus", "membrane", "eukaryotic", "prokaryotic"],
        topic="Cell Biology",
        points=4.0,
    )

    rubric = (
        Rubric("Biology Essay Rubric")
        .add_criterion("Scientific Accuracy", 8.0, "Correctness of biological facts")
        .add_criterion("Critical Analysis", 7.0, "Depth of analysis and reasoning")
        .add_criterion("Communication", 5.0, "Clarity and organization of writing")
        .build()
    )

    essay1 = EssayGenerator.build_question(
        text="Evaluate the significance of mitochondrial DNA in evolutionary biology.",
        sample_answer="Mitochondrial DNA provides evidence for endosymbiotic theory...",
        rubric=rubric,
        topic="Cell Biology",
        points=20.0,
    )
    essay1.keywords = ["mitochondrial", "DNA", "evolution", "endosymbiotic", "maternal"]

    exam = Exam(
        id="bio-101-midterm",
        title="Biology 101 Midterm",
        description="Cell biology fundamentals",
        topic="Cell Biology",
        questions=[mcq1, mcq2, sa1, essay1],
        time_limit_minutes=60,
    )

    console.print(f"Exam: {exam.title}")
    console.print(f"Questions: {exam.question_count} | Total points: {exam.total_points}\n")

    # Show Bloom levels
    for q in exam.questions:
        level = BloomTaxonomy.classify(q)
        console.print(f"  [{level.value.upper():10s}] {q.text[:70]}")
    console.print()

    # ── 2. Simulate a student submission ────────────────────────
    submission = ExamSubmission(
        exam_id=exam.id,
        student_id="jane-doe-42",
        answers=[
            Answer(question_id=mcq1.id, response="B", selected_option="B"),
            Answer(question_id=mcq2.id, response="A", selected_option="A"),  # wrong
            Answer(
                question_id=sa1.id,
                response=(
                    "Eukaryotic cells possess a membrane-bound nucleus, "
                    "while prokaryotic cells lack this structure."
                ),
            ),
            Answer(
                question_id=essay1.id,
                response=(
                    "Mitochondrial DNA is inherited exclusively through the maternal line, "
                    "making it a powerful tool for tracing evolution. The endosymbiotic theory "
                    "posits that mitochondria were once free-living organisms that entered "
                    "a symbiotic relationship with ancestral eukaryotic cells."
                ),
            ),
        ],
    )

    # ── 3. Grade ────────────────────────────────────────────────
    console.print("[bold blue]Grading...[/bold blue]\n")

    auto_grader = AutoGrader(keyword_partial_credit=True)
    report = auto_grader.grade(exam, submission)

    # Grade essay via keyword fallback (no LLM needed)
    essay_answer = submission.answer_for(essay1.id)
    if essay_answer:
        essay_result = EssayGrader.grade_by_keywords(essay1, essay_answer)
        report.results.append(essay_result)

    # ── 4. Rich report ──────────────────────────────────────────
    render_grade_report(report, exam, console=console)


if __name__ == "__main__":
    main()
