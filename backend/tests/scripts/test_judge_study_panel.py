from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.metrics import (
    agreement_with_panel,
    panel_reference,
    reference_matrix,
    reliability_bins,
)
from judge_study.results import Failure, Judgement, OutputItem, Results


def _item(item_id: str, panel: tuple[int, int] | None = None, llm: int | None = None, decision: int | None = None):
    judgements = []
    if panel:
        for name, score in zip(("panel_claude", "panel_gpt"), panel, strict=True):
            judgements.append(Judgement(judge=name, repeat=1, score=score, model="m", latency_s=1))
    for name, score in (("llm", llm), ("decision", decision)):
        if score:
            judgements.append(Judgement(judge=name, repeat=1, score=score, model="m", latency_s=1))
    return OutputItem(item_id=item_id, feature="meal_plan", input={}, output={}, judge_inputs={}, judgements=judgements)


class TestPanelReference:
    def test_equal_panel_scores_are_the_reference(self) -> None:
        reference = panel_reference(_item("a", (4, 4)))

        assert (reference.score, reference.contested) == (4, False)

    def test_scores_one_apart_use_their_mean(self) -> None:
        reference = panel_reference(_item("a", (4, 5)))

        assert (reference.score, reference.contested) == (4.5, False)

    def test_scores_two_or_more_apart_are_contested_and_have_no_reference(self) -> None:
        reference = panel_reference(_item("a", (2, 4)))

        assert (reference.score, reference.contested) == (None, True)

    def test_an_item_the_panel_did_not_score_has_no_reference_and_is_not_contested(self) -> None:
        reference = panel_reference(_item("a"))

        assert (reference.score, reference.contested) == (None, False)


def _scored(item_id: str, panel: tuple[int, int], candidate: int) -> OutputItem:
    return _item(item_id, panel, decision=candidate)


class TestAgreementWithPanel:
    def test_exact_means_equal_to_the_panel_mean_so_a_half_point_reference_is_never_matched(self) -> None:
        assert agreement_with_panel([_scored("a", (4, 4), 4)], "decision").exact == 1.0
        assert agreement_with_panel([_scored("a", (4, 5), 4)], "decision").exact == 0.0
        assert agreement_with_panel([_scored("a", (4, 5), 5)], "decision").exact == 0.0

    def test_within_one_is_measured_from_the_mean(self) -> None:
        # Worked by hand: |4 - 4.5| = 0.5, |5 - 4.5| = 0.5, |3 - 4.5| = 1.5, |2 - 4| = 2.
        assert agreement_with_panel([_scored("a", (4, 5), 4)], "decision").within_one == 1.0
        assert agreement_with_panel([_scored("a", (4, 5), 5)], "decision").within_one == 1.0
        assert agreement_with_panel([_scored("a", (4, 5), 3)], "decision").within_one == 0.0
        assert agreement_with_panel([_scored("a", (4, 4), 2)], "decision").within_one == 0.0

    def test_contested_items_are_left_out_of_the_figures(self) -> None:
        items = [_scored("a", (4, 4), 4), _scored("b", (1, 4), 4)]

        assert agreement_with_panel(items, "decision").n == 1

    def test_kappa_keeps_the_half_point_reference_with_squared_distance_weights(self) -> None:
        # Candidate 1,3,5,4 against references 1,3,5,4.5. Worked independently with
        # 2*Cov(X,Y) / (Var X + Var Y + (mean X - mean Y)^2) = 0.98648648...
        items = [
            _scored("a", (1, 1), 1),
            _scored("b", (3, 3), 3),
            _scored("c", (5, 5), 5),
            _scored("d", (4, 5), 4),
        ]

        assert agreement_with_panel(items, "decision").kappa == pytest.approx(0.9864864864864865)

    def test_only_outputs_the_candidate_scored_count(self) -> None:
        assert agreement_with_panel([_item("a", (4, 4))], "decision").n == 0


class TestReferenceMatrix:
    def test_columns_run_from_one_to_five_in_half_points(self) -> None:
        matrix = reference_matrix([(5, 4.5), (4, 4), (1, 1)])

        assert len(matrix) == 5
        assert all(len(row) == 9 for row in matrix)
        assert matrix[4][7] == 1  # candidate 5, reference 4.5
        assert matrix[3][6] == 1  # candidate 4, reference 4
        assert matrix[0][0] == 1


class TestReliabilityAgainstPanel:
    def test_a_match_is_equal_to_the_panel_mean_and_contested_outputs_are_left_out(self) -> None:
        def decided(item_id: str, panel: tuple[int, int], score: int, confidence: float) -> OutputItem:
            item = _item(item_id, panel)
            item.judgements.append(
                Judgement(judge="decision", repeat=1, score=score, model="m", latency_s=1, confidence=confidence)
            )
            return item

        items = [
            decided("hit", (4, 4), 4, 0.9),
            decided("half-point", (4, 5), 5, 0.9),  # reference 4.5: never a match
            decided("miss", (2, 2), 4, 0.9),
            decided("contested", (1, 4), 4, 0.9),
        ]

        (only,) = reliability_bins(items, bins=1, reference="panel")

        assert (only.n, only.accuracy) == (3, pytest.approx(1 / 3))


def test_failures_are_kept_in_the_results_file(tmp_path: Path) -> None:
    failure = Failure(judge="llm", item_id="meal_plan/0/0", repeat=2, error="OutputParserException: empty answer")
    results = Results(models={}, items=[], failures=[failure])

    results.save(tmp_path / "r.json")

    assert Results.load(tmp_path / "r.json").failures == [failure]
