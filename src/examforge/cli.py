"""Click CLI for ExamForge: generate, grade, report."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import click
from rich.console import Console

from examforge.models import (
    Answer,
    BloomLevel,
    Difficulty,
    Exam,
    ExamSubmission,
    GradeReport,
    Question,
    QuestionType,
)

console = Console()


def _get_openai_client():
    """Lazily create an OpenAI client; returns None if the package or key is missing."""
    try:
        import openai  # noqa: F811

        return openai.OpenAI()
    except Exception:
        return None


@click.group()
@click.version_option(package_name="examforge")
def cli() -> None:
    """ExamForge -- AI-powered exam generation, grading, and reporting."""


# ── generate ────────────────────────────────────────────────────


@cli.command()
@click.option("--topic", required=True, help="Subject topic for the exam.")
@click.option("--mcq", "mcq_count", default=0, type=int, help="Number of MCQs.")
@click.option("--short", "short_count", default=0, type=int, help="Number of short-answer questions.")
@click.option("--essay", "essay_count", default=0, type=int, help="Number of essay prompts.")
@click.option(
    "--difficulty",
    type=click.Choice(["easy", "medium", "hard"], case_sensitive=False),
    default="medium",
)
@click.option(
    "--bloom",
    type=click.Choice([b.value for b in BloomLevel], case_sensitive=False),
    default=None,
    help="Target Bloom's taxonomy level.",
)
@click.option("--context", type=click.Path(exists=True), default=None, help="Path to source material text file.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output JSON file path.")
def generate(
    topic: str,
    mcq_count: int,
    short_count: int,
    essay_count: int,
    difficulty: str,
    bloom: str | None,
    context: str | None,
    output: str | None,
) -> None:
    """Generate an exam from a topic."""
    from examforge.generator.essay import EssayGenerator
    from examforge.generator.mcq import MCQGenerator
    from examforge.generator.short_answer import ShortAnswerGenerator

    diff = Difficulty(difficulty)
    bloom_level = BloomLevel(bloom) if bloom else None
    context_text = Path(context).read_text() if context else None

    client = _get_openai_client()
    if client is None:
        console.print(
            "[yellow]Warning:[/yellow] No OpenAI client available. "
            "Set the OPENAI_API_KEY environment variable for LLM-powered generation.",
        )

    questions: list[Question] = []

    if mcq_count > 0:
        console.print(f"Generating {mcq_count} MCQ(s)...")
        gen = MCQGenerator(client=client)
        try:
            questions.extend(gen.generate(topic, mcq_count, diff, bloom_level, context_text))
        except RuntimeError as exc:
            console.print(f"[red]MCQ generation failed:[/red] {exc}")

    if short_count > 0:
        console.print(f"Generating {short_count} short-answer question(s)...")
        gen_sa = ShortAnswerGenerator(client=client)
        try:
            questions.extend(gen_sa.generate(topic, short_count, diff, bloom_level, context_text))
        except RuntimeError as exc:
            console.print(f"[red]Short-answer generation failed:[/red] {exc}")

    if essay_count > 0:
        console.print(f"Generating {essay_count} essay prompt(s)...")
        gen_essay = EssayGenerator(client=client)
        try:
            questions.extend(gen_essay.generate(topic, essay_count, diff, bloom_level, context_text))
        except RuntimeError as exc:
            console.print(f"[red]Essay generation failed:[/red] {exc}")

    if not questions:
        console.print("[red]No questions generated.[/red]")
        sys.exit(1)

    exam = Exam(
        id=f"exam-{uuid.uuid4().hex[:8]}",
        title=f"{topic} Exam",
        topic=topic,
        questions=questions,
    )

    data = exam.model_dump(mode="json")
    if output:
        Path(output).write_text(json.dumps(data, indent=2))
        console.print(f"[green]Exam written to {output}[/green]")
    else:
        console.print_json(json.dumps(data, indent=2))

    console.print(
        f"\n[bold]Generated {len(questions)} question(s) | "
        f"Total points: {exam.total_points}[/bold]"
    )


# ── grade ───────────────────────────────────────────────────────


@cli.command()
@click.option("--exam", "exam_path", required=True, type=click.Path(exists=True), help="Exam JSON file.")
@click.option("--submission", required=True, type=click.Path(exists=True), help="Submission JSON file.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output results JSON file.")
def grade(exam_path: str, submission: str, output: str | None) -> None:
    """Grade a student submission against an exam."""
    from examforge.grader.auto_grader import AutoGrader
    from examforge.grader.essay_grader import EssayGrader

    exam_data = json.loads(Path(exam_path).read_text())
    sub_data = json.loads(Path(submission).read_text())

    exam = Exam.model_validate(exam_data)
    sub = ExamSubmission.model_validate(sub_data)

    # Auto-grade MCQ and short-answer.
    grader = AutoGrader(keyword_partial_credit=True)
    report = grader.grade(exam, sub)

    # Attempt LLM essay grading; fall back to keyword grading.
    essay_questions = exam.questions_by_type(QuestionType.ESSAY)
    if essay_questions:
        client = _get_openai_client()
        essay_grader = EssayGrader(client=client)
        for eq in essay_questions:
            answer = sub.answer_for(eq.id)
            if answer is None:
                continue
            try:
                if client:
                    result = essay_grader.grade(eq, answer)
                else:
                    result = EssayGrader.grade_by_keywords(eq, answer)
                report.results.append(result)
            except Exception as exc:
                console.print(f"[yellow]Essay grading warning:[/yellow] {exc}")

    data = report.model_dump(mode="json")
    if output:
        Path(output).write_text(json.dumps(data, indent=2))
        console.print(f"[green]Results written to {output}[/green]")
    else:
        console.print_json(json.dumps(data, indent=2))

    console.print(
        f"\n[bold]Score: {report.total_earned:.1f}/{report.total_possible:.1f} "
        f"({report.percentage:.1f}%) -- {report.letter_grade}[/bold]"
    )


# ── report ──────────────────────────────────────────────────────


@cli.command()
@click.option("--results", required=True, type=click.Path(exists=True), help="Grade results JSON file.")
@click.option("--exam", "exam_path", required=True, type=click.Path(exists=True), help="Original exam JSON file.")
def report(results: str, exam_path: str) -> None:
    """Display a rich grade report in the terminal."""
    from examforge.report import render_grade_report

    report_data = json.loads(Path(results).read_text())
    exam_data = json.loads(Path(exam_path).read_text())

    grade_report = GradeReport.model_validate(report_data)
    exam = Exam.model_validate(exam_data)

    render_grade_report(grade_report, exam, console=console)


if __name__ == "__main__":
    cli()
