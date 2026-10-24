"""What an enrichment run found and did, printed as a table and readable as data.

Per question: how many recipes have a current answer, a stale one, none at all, or were asked and failed
this run. Plus the run's totals — requests made, answers stored, and how many recipes state an active
time, which is the number the coverage report is also there to put on (spec 6.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glean.recipes.enrichment.enricher import ConfidenceBar

__all__ = ["AnswerFailure", "CoverageReport", "QuestionCoverage"]


@dataclass(frozen=True)
class AnswerFailure:
    """A recipe the model couldn't answer. Not fatal: the recipe stays uncovered and the next run retries."""

    recipe_id: str
    question: str
    error: str


@dataclass
class QuestionCoverage:
    """How every recipe in the corpus stands against one question."""

    name: str
    bar: ConfidenceBar
    current: int = 0
    stale: int = 0
    missing: int = 0
    failed: int = 0

    @property
    def recipes(self) -> int:
        return self.current + self.stale + self.missing + self.failed


@dataclass
class CoverageReport:
    """The outcome of one enrichment run.

    `requests` and `answers_stored` are what the run cost; everything else describes the corpus after it.
    """

    recipes: int
    questions: list[QuestionCoverage]
    requests: int = 0
    answers_stored: int = 0
    stated_prep_time: int = 0
    rebuilt: bool = False
    dry_run: bool = False
    planned_requests: int = 0
    incomplete: list[str] = field(default_factory=list)
    failures: list[AnswerFailure] = field(default_factory=list)

    def question(self, name: str) -> QuestionCoverage:
        return next(coverage for coverage in self.questions if coverage.name == name)

    @property
    def expected(self) -> int:
        return self.recipes * len(self.questions)

    @property
    def covered(self) -> int:
        return sum(coverage.current for coverage in self.questions)

    @property
    def coverage(self) -> float:
        return self.covered / self.expected if self.expected else 1.0

    @property
    def failed(self) -> int:
        return sum(coverage.failed for coverage in self.questions)

    def render(self) -> str:
        lines = [
            f"Recipes: {self.recipes}   Questions: {len(self.questions)}   "
            f"Requests: {self.requests}   Answers stored: {self.answers_stored}",
            _table(self.questions),
        ]
        if self.dry_run:
            lines.append(f"Dry run: {self.planned_requests} recipes would be asked; nothing was requested or stored.")
        if self.failures:
            lines.append(f"Failed this run: {len(self.failures)} ({_summarise(self.failures)})")
        lines.append(f"Recipes with a stated prep time: {_ratio(self.stated_prep_time, self.recipes)}")
        lines.append(f"Coverage: {self.covered}/{self.expected} ({self.coverage:.1%})")
        if self.recipes:
            lines.append("Projection: rebuilt" if self.rebuilt else "Projection: not rebuilt, nothing was written")
        if self.incomplete:
            shown = ", ".join(self.incomplete[:5])
            more = "" if len(self.incomplete) <= 5 else f", and {len(self.incomplete) - 5} more"
            lines.append(f"Recipes without full coverage ({len(self.incomplete)}): {shown}{more}")
        return "\n".join(lines)


_COLUMNS = ("question", "current", "stale", "missing", "failed", "bar")


def _table(questions: list[QuestionCoverage]) -> str:
    rows = [
        (
            coverage.name,
            str(coverage.current),
            str(coverage.stale),
            str(coverage.missing),
            str(coverage.failed),
            f"{coverage.bar.threshold:.2f} ({coverage.bar.safe_side})",
        )
        for coverage in questions
    ]
    widths = [max(len(row[index]) for row in [*rows, _COLUMNS]) for index in range(len(_COLUMNS))]
    lines = []
    for row in [_COLUMNS, *rows]:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=True)]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def _summarise(failures: list[AnswerFailure]) -> str:
    first = failures[0]
    return f"{first.recipe_id} {first.question}: {first.error[:80]}"


def _ratio(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole:.1%})" if whole else "0/0"
