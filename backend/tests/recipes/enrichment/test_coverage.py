"""The coverage report: what a run found, printed as a table and readable as data (spec 6.1)."""

from __future__ import annotations

from glean.recipes.enrichment import ConfidenceBar, CoverageReport, QuestionCoverage, SafeSide


def test_the_table_lists_every_question_with_its_counts_and_its_bar() -> None:
    report = _report()

    rendered = report.render()
    header, first = rendered.splitlines()[1:3]

    assert header.split() == ["question", "current", "stale", "missing", "failed", "bar"]
    assert first.split() == ["dietary:vegan", "3", "1", "0", "0", "0.50", "(low)"]
    assert "Recipes: 4   Questions: 2   Requests: 5   Answers stored: 6" in rendered
    assert "Coverage: 4/8 (50.0%)" in rendered


def test_the_report_is_readable_as_data_not_just_as_text() -> None:
    report = _report()

    coverage = report.question("dietary:vegan")
    assert (coverage.current, coverage.stale, coverage.missing, coverage.failed) == (3, 1, 0, 0)
    assert coverage.recipes == 4  # every recipe sits in exactly one bucket
    assert (report.covered, report.expected, report.coverage, report.failed) == (4, 8, 0.5, 1)
    assert report.stated_prep_time == 4


def test_the_report_states_how_many_recipes_give_a_prep_time() -> None:
    assert "Recipes with a stated prep time: 4/4 (100.0%)" in _report().render()


def test_recipes_without_full_coverage_are_named_but_not_all_listed() -> None:
    report = _report(incomplete=[f"rec_{index}" for index in range(7)])

    assert "Recipes without full coverage (7): rec_0, rec_1, rec_2, rec_3, rec_4, and 2 more" in report.render()


def test_a_dry_run_says_what_it_would_have_asked() -> None:
    report = CoverageReport(
        recipes=4,
        questions=[QuestionCoverage("dietary:vegan", _bar())],
        dry_run=True,
        planned_requests=3,
    )

    rendered = report.render()
    assert "Dry run: 3 recipes would be asked; nothing was requested or stored." in rendered
    assert "Projection: not rebuilt, nothing was written" in rendered


def test_a_run_that_wrote_says_so_about_the_projection() -> None:
    report = CoverageReport(recipes=1, questions=[QuestionCoverage("dietary:vegan", _bar())], rebuilt=True)

    assert "Projection: rebuilt" in report.render()


def test_a_corpus_with_no_recipes_reads_as_complete_rather_than_dividing_by_zero() -> None:
    report = CoverageReport(recipes=0, questions=[QuestionCoverage("dietary:vegan", _bar())])

    assert (report.expected, report.coverage) == (0, 1.0)
    assert "Recipes with a stated prep time: 0/0" in report.render()


def test_a_failure_is_summarised_by_one_example() -> None:
    from glean.recipes.enrichment import AnswerFailure  # noqa: PLC0415 - only this test needs it

    report = _report(failures=[AnswerFailure("rec_7", "dietary:vegan", "HTTP 500: the endpoint is down")])

    assert "Failed this run: 1 (rec_7 dietary:vegan: HTTP 500" in report.render()


def _bar() -> ConfidenceBar:
    return ConfidenceBar(threshold=0.5, safe_side=SafeSide.LOW)


def _report(*, incomplete: list[str] | None = None, failures: list | None = None) -> CoverageReport:
    return CoverageReport(
        recipes=4,
        questions=[
            QuestionCoverage("dietary:vegan", _bar(), current=3, stale=1),
            QuestionCoverage("dietary:tree-nut-free", ConfidenceBar(0.3, SafeSide.LOW), current=1, missing=2, failed=1),
        ],
        requests=5,
        answers_stored=6,
        stated_prep_time=4,
        rebuilt=True,
        incomplete=["rec_3"] if incomplete is None else incomplete,
        failures=[] if failures is None else failures,
    )
