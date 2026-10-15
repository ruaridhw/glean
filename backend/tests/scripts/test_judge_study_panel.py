from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.metrics import agreement_with_panel, panel_reference
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


class TestAgreementWithPanel:
    def test_a_candidate_matches_exactly_when_it_equals_either_panel_score(self) -> None:
        items = [
            _item("a", (4, 4), decision=4),
            _item("b", (4, 5), decision=5),
            _item("c", (4, 5), decision=3),
            _item("d", (2, 2), decision=4),
        ]

        result = agreement_with_panel(items, "decision")

        assert result.n == 4
        assert result.exact == 0.5
        assert result.within_one == 0.75  # 3 is within one of the panel's 4; 4 is two from the panel's 2

    def test_contested_items_are_left_out_of_the_figures(self) -> None:
        items = [_item("a", (4, 4), decision=4), _item("b", (1, 4), decision=4)]

        assert agreement_with_panel(items, "decision").n == 1

    def test_kappa_uses_the_reference_rounded_half_up(self) -> None:
        items = [
            _item("a", (1, 1), decision=1),
            _item("b", (5, 5), decision=5),
            _item("c", (2, 3), decision=3),  # reference 2.5 -> 3
            _item("d", (3, 3), decision=3),
        ]

        assert agreement_with_panel(items, "decision").kappa == pytest.approx(1.0)

    def test_only_outputs_the_candidate_scored_count(self) -> None:
        assert agreement_with_panel([_item("a", (4, 4))], "decision").n == 0


def test_failures_are_kept_in_the_results_file(tmp_path: Path) -> None:
    failure = Failure(judge="llm", item_id="meal_plan/0/0", repeat=2, error="OutputParserException: empty answer")
    results = Results(models={}, items=[], failures=[failure])

    results.save(tmp_path / "r.json")

    assert Results.load(tmp_path / "r.json").failures == [failure]
