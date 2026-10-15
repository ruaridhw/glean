from __future__ import annotations

import pytest
from scripts.eval_normalisation import (
    Grade,
    Label,
    Outcome,
    Prediction,
    classify,
    grade_result,
    metrics_at,
    pick_threshold,
)


def label(expected: str | None, *also: str, groups: tuple[str, ...] = ()) -> Label:
    return Label(input="x", expected=expected, also_acceptable=also, expected_groups=groups)


@pytest.mark.parametrize(
    ("row", "predicted", "outcome"),
    [
        (label("coriander"), "coriander", Outcome.CORRECT),
        (label("tinned chickpeas", "dried chickpeas"), "dried chickpeas", Outcome.CORRECT),
        (label("coriander"), None, Outcome.DUPLICATE),
        (label("coriander"), "dried coriander", Outcome.FALSE_MATCH),
        (label(None), None, Outcome.CORRECT),
        (label(None), "milk", Outcome.FALSE_MATCH),
        (label(None, "surface cleaner"), "surface cleaner", Outcome.CORRECT),
        (label("NONSENSE"), None, Outcome.CORRECT),
        (label("NONSENSE"), "salt", Outcome.FALSE_MATCH),
    ],
)
def test_classify_scores_a_prediction_against_its_label(row: Label, predicted: str | None, outcome: Outcome) -> None:
    assert classify(row, predicted) is outcome


def prediction(choice: str | None, probability: float) -> Prediction:
    return Prediction(match=choice, probability=probability, kind_agrees=True)


def test_a_higher_threshold_trades_false_matches_for_duplicates() -> None:
    rows = [label("coriander"), label(None), label("lime")]
    predictions = [prediction("coriander", 0.9), prediction("milk", 0.6), prediction("lime", 0.65)]

    low = metrics_at(rows, predictions, 0.5)
    high = metrics_at(rows, predictions, 0.8)

    assert (low.false_matches, low.duplicates, low.correct) == (1, 0, 2)
    assert (high.false_matches, high.duplicates, high.correct) == (0, 1, 2)


def test_the_lowest_threshold_within_the_false_match_budget_is_picked() -> None:
    rows = [label("coriander"), label(None), label("lime")]
    predictions = [prediction("coriander", 0.9), prediction("milk", 0.6), prediction("lime", 0.65)]

    assert pick_threshold(rows, predictions, max_false_match_rate=0.0, grid=[0.5, 0.6, 0.7, 0.8]) == 0.7
    assert pick_threshold(rows, predictions, max_false_match_rate=1.0, grid=[0.5, 0.6, 0.7]) == 0.5


def test_a_kind_mismatch_is_never_a_match() -> None:
    rows = [label(None)]
    predictions = [Prediction(match="coriander", probability=0.99, kind_agrees=False)]

    assert metrics_at(rows, predictions, 0.5).false_matches == 0


@pytest.mark.parametrize(
    ("row", "got", "grade"),
    [
        (label("coriander"), ("matched", "coriander", "fresh_herbs", "ingredient"), Grade.CORRECT),
        (label("coriander"), ("created", "cilantro", "fresh_herbs", "ingredient"), Grade.DUPLICATE),
        (label("coriander"), ("matched", "basil", "fresh_herbs", "ingredient"), Grade.FALSE_MATCH),
        (label("coriander"), ("unresolved", "x", None, None), Grade.UNRESOLVED),
        (label(None, groups=("drinks",)), ("created", "berry juice", "drinks", "ingredient"), Grade.CORRECT),
        (
            label(None, groups=("household",)),
            ("created", "rim blocks", "snacks_and_treats", "ingredient"),
            Grade.KIND_ERROR,
        ),
        (label(None, groups=("dairy",)), ("created", "skyr", "snacks_and_treats", "ingredient"), Grade.WRONG_GROUP),
        (label(None, groups=("dairy",)), ("matched", "natural yogurt", "dairy", "ingredient"), Grade.FALSE_MATCH),
        (
            label(None, "surface cleaner", groups=("household",)),
            ("matched", "surface cleaner", "household", "household_item"),
            Grade.CORRECT,
        ),
        (label(None, groups=("dairy",)), ("unmatched", "x", None, None), Grade.WRONG_UNMATCHED),
        (label("NONSENSE"), ("unmatched", "asdkjh", None, None), Grade.CORRECT),
        (label("NONSENSE"), ("created", "asdkjh", "other", "ingredient"), Grade.NONSENSE_NAMED),
        (label("NONSENSE"), ("matched", "salt", "spices", "ingredient"), Grade.FALSE_MATCH),
    ],
)
def test_grade_scores_a_whole_pipeline_result_against_its_label(
    row: Label, got: tuple[str, str, str | None, str | None], grade: Grade
) -> None:
    status, canonical, group, kind = got

    assert grade_result(row, status=status, canonical=canonical, group=group, kind=kind) is grade
