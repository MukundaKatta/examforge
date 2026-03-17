"""Rich terminal grade reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from examforge.models import (
    BloomLevel,
    Exam,
    GradeReport,
    QuestionType,
)


def _pct_color(pct: float) -> str:
    if pct >= 90:
        return "bold green"
    if pct >= 80:
        return "green"
    if pct >= 70:
        return "yellow"
    if pct >= 60:
        return "dark_orange"
    return "bold red"


def render_grade_report(
    report: GradeReport,
    exam: Exam,
    console: Console | None = None,
) -> None:
    """Print a rich grade report to the terminal.

    Args:
        report: The grading results.
        exam: The original exam (needed for question metadata).
        console: Optional Rich console; a new one is created if not given.
    """
    con = console or Console()
    q_map = {q.id: q for q in exam.questions}

    # ── Header ──────────────────────────────────────────────────
    pct = report.percentage
    grade_text = Text(f"  {report.letter_grade}  ", style=f"{_pct_color(pct)} reverse")
    header = Text.assemble(
        ("Student: ", "bold"),
        report.student_id,
        "  |  ",
        ("Score: ", "bold"),
        f"{report.total_earned:.1f}/{report.total_possible:.1f} ({pct:.1f}%)  ",
        grade_text,
    )
    con.print(Panel(header, title=f"[bold]{exam.title}[/bold]", border_style="blue"))

    # ── Per-question table ──────────────────────────────────────
    table = Table(title="Question Breakdown", show_lines=True, expand=True)
    table.add_column("#", justify="center", width=4)
    table.add_column("Type", justify="center", width=8)
    table.add_column("Bloom", justify="center", width=10)
    table.add_column("Question", ratio=3)
    table.add_column("Score", justify="right", width=12)
    table.add_column("Feedback", ratio=2)

    for idx, result in enumerate(report.results, start=1):
        q = q_map.get(result.question_id)
        qtype = q.type.value.upper() if q else "?"
        bloom = q.bloom_level.value.capitalize() if q else "?"
        text_preview = (q.text[:80] + "...") if q and len(q.text) > 80 else (q.text if q else "?")
        score_str = f"{result.points_earned:.1f}/{result.points_possible:.1f}"
        score_style = _pct_color(result.percentage)
        feedback = result.feedback[:120] or "-"

        table.add_row(
            str(idx),
            qtype,
            bloom,
            text_preview,
            Text(score_str, style=score_style),
            feedback,
        )

    con.print(table)

    # ── Bloom distribution ──────────────────────────────────────
    bloom_counts: dict[BloomLevel, int] = {}
    for q in exam.questions:
        bloom_counts[q.bloom_level] = bloom_counts.get(q.bloom_level, 0) + 1

    if bloom_counts:
        bloom_table = Table(title="Bloom's Taxonomy Distribution", show_lines=False)
        bloom_table.add_column("Level", justify="left", width=12)
        bloom_table.add_column("Count", justify="center", width=8)
        bloom_table.add_column("Bar", ratio=2)
        total = len(exam.questions) or 1
        for level in BloomLevel:
            count = bloom_counts.get(level, 0)
            bar = "#" * int((count / total) * 30)
            bloom_table.add_row(level.value.capitalize(), str(count), bar)
        con.print(bloom_table)

    # ── Per-type summary ────────────────────────────────────────
    grouped = report.results_by_type(exam)
    if grouped:
        type_table = Table(title="Score by Question Type", show_lines=False)
        type_table.add_column("Type", justify="left", width=14)
        type_table.add_column("Earned", justify="right", width=10)
        type_table.add_column("Possible", justify="right", width=10)
        type_table.add_column("%", justify="right", width=8)

        for qtype in QuestionType:
            results = grouped.get(qtype, [])
            if results:
                earned = sum(r.points_earned for r in results)
                possible = sum(r.points_possible for r in results)
                type_pct = (earned / possible * 100) if possible else 0
                type_table.add_row(
                    qtype.value.upper(),
                    f"{earned:.1f}",
                    f"{possible:.1f}",
                    Text(f"{type_pct:.0f}%", style=_pct_color(type_pct)),
                )
        con.print(type_table)

    # ── Essay criterion details ─────────────────────────────────
    essay_results = [r for r in report.results if r.criterion_scores]
    if essay_results:
        for result in essay_results:
            q = q_map.get(result.question_id)
            title = f"Essay: {q.text[:60]}..." if q and len(q.text) > 60 else f"Essay: {q.text if q else '?'}"
            crit_table = Table(title=title, show_lines=False)
            crit_table.add_column("Criterion", ratio=2)
            crit_table.add_column("Score", justify="right", width=10)

            rubric = q.rubric if q else None
            max_map = {c.name: c.max_points for c in rubric.criteria} if rubric else {}
            for crit_name, score in result.criterion_scores.items():
                max_pts = max_map.get(crit_name, score)
                crit_table.add_row(crit_name, f"{score:.1f}/{max_pts:.1f}")
            con.print(crit_table)
