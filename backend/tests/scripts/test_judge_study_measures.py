from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.metrics import (
    cost_summary,
    disagreements,
    drift,
    item_score,
    judge_pairs,
    latency_summary,
    reliability_bins,
    study_spend,
)
from judge_study.results import Attempt, Judgement, OutputItem, Results


def _item(
    item_id: str = "x",
    llm: list[int] | None = None,
    decision: list[int] | None = None,
    human: int | None = None,
    confidence: list[float] | None = None,
    cost: float | None = None,
    latency: float = 1.0,
) -> OutputItem:
    judgements = [
        Judgement(judge="llm", repeat=i, score=s, model="m", latency_s=latency, cost_usd=cost)
        for i, s in enumerate(llm or [], start=1)
    ]
    for i, s in enumerate(decision or [], start=1):
        judgements.append(
            Judgement(
                judge="decision",
                repeat=i,
                score=s,
                model="d",
                latency_s=latency,
                cost_usd=cost,
                confidence=(confidence or [0.5] * 9)[i - 1],
            )
        )
    return OutputItem(
        item_id=item_id,
        feature="meal_plan",
        input={},
        output={},
        judge_inputs={},
        judgements=judgements,
        human_score=human,
    )


class TestItemScore:
    def test_a_judges_score_for_an_output_is_the_median_of_its_repeats(self) -> None:
        assert item_score(_item(llm=[2, 5, 4]), "llm") == 4

    def test_the_human_score_is_the_humans(self) -> None:
        assert item_score(_item(human=3), "human") == 3

    def test_an_unscored_output_has_no_score(self) -> None:
        assert item_score(_item(), "decision") is None
        assert item_score(_item(), "human") is None


class TestJudgePairs:
    def test_only_outputs_scored_by_both_judges_are_paired(self) -> None:
        items = [_item("a", llm=[4, 4, 4], decision=[5, 5, 5]), _item("b", llm=[3]), _item("c", decision=[2])]

        assert judge_pairs(items, "llm", "decision") == [(4, 5)]

    def test_the_human_can_be_either_side(self) -> None:
        items = [_item("a", decision=[4], human=2)]

        assert judge_pairs(items, "human", "decision") == [(2, 4)]


class TestDisagreements:
    def test_lists_outputs_where_the_judges_differ_widest_first(self) -> None:
        items = [
            _item("same", llm=[4], decision=[4]),
            _item("near", llm=[4], decision=[5]),
            _item("far", llm=[1], decision=[5]),
        ]

        assert [item.item_id for item in disagreements(items)] == ["far", "near"]


class TestReliabilityBins:
    def test_each_bin_compares_the_judges_confidence_with_how_often_it_matched_the_human(self) -> None:
        items = [
            _item("a", decision=[5, 5, 5], human=5, confidence=[0.9, 0.9, 0.9]),
            _item("b", decision=[5, 5, 5], human=3, confidence=[0.9, 0.95, 0.85]),
            _item("c", decision=[2, 2, 2], human=2, confidence=[0.3, 0.3, 0.3]),
            _item("d", decision=[2, 2, 2], human=4, confidence=[0.35, 0.35, 0.35]),
        ]

        low, high = reliability_bins(items, bins=2)

        assert (low.n, low.accuracy, low.mean_confidence) == (2, 0.5, pytest.approx(0.325))
        assert (high.n, high.accuracy, high.mean_confidence) == (2, 0.5, pytest.approx(0.9))

    def test_outputs_without_a_human_score_or_confidence_are_left_out(self) -> None:
        assert reliability_bins([_item(decision=[4]), _item(decision=[4], human=None)], bins=5) == []

    def test_a_confidence_of_exactly_one_lands_in_the_top_bin(self) -> None:
        (only,) = reliability_bins([_item(decision=[4], human=4, confidence=[1.0])], bins=5)

        assert (only.upper, only.n) == (1.0, 1)


class TestDrift:
    def test_it_reports_how_often_repeats_disagree_and_by_how_much(self) -> None:
        items = [_item("steady", llm=[4, 4, 4]), _item("wobbly", llm=[2, 4, 5]), _item("once", llm=[3])]

        result = drift(items, "llm")

        assert result.items == 2  # a single run can't drift
        assert result.identical_share == 0.5
        assert result.mean_range == pytest.approx(1.5)
        assert result.max_range == 3


class TestStudySpend:
    def test_a_priced_ledger_is_counted_once_and_a_judgement_with_ledger_entries_is_not_added_again(self) -> None:
        item = _item("a", llm=[4], cost=0.002)
        attempts = [
            Attempt(
                judge="llm", item_id="a", repeat=1, attempt=1, outcome="parse_failure", latency_s=1, cost_usd=0.002
            ),
            Attempt(judge="llm", item_id="a", repeat=1, attempt=2, outcome="ok", latency_s=1, cost_usd=0.002),
        ]

        spend = study_spend(Results(models={}, items=[item], attempts=attempts))

        assert (spend.known, spend.unpriced_calls) == (pytest.approx(0.004), 0)

    def test_legacy_judgements_without_ledger_entries_are_added_once_and_unknown_ones_are_counted(self) -> None:
        priced, unpriced = _item("a", llm=[4], cost=0.002), _item("b", llm=[4], cost=None)

        spend = study_spend(Results(models={}, items=[priced, unpriced]))

        assert (spend.known, spend.unpriced_calls) == (pytest.approx(0.002), 1)

    def test_unpriced_ledger_calls_are_counted_not_summed_as_zero(self) -> None:
        attempts = [Attempt(judge="llm", item_id="a", repeat=1, attempt=1, outcome="call_failure", latency_s=1)]

        spend = study_spend(Results(models={}, items=[_item("a")], attempts=attempts))

        assert (spend.known, spend.unpriced_calls) == (0.0, 1)


class TestCostAndLatency:
    def test_cost_is_per_judgement_and_counts_the_ones_that_reported_none(self) -> None:
        items = [_item("a", llm=[4, 4], cost=0.002), _item("b", llm=[4], cost=None)]

        summary = cost_summary(items, "llm")

        assert summary.judgements == 3
        assert summary.total == pytest.approx(0.004)
        assert summary.mean == pytest.approx(0.002)
        assert summary.unreported == 1

    def test_a_judgement_with_an_unpriced_attempt_is_left_out_of_the_full_cost_mean(self) -> None:
        complete = _item("a", llm=[4], cost=0.002)
        partial = _item("b", llm=[4], cost=0.001)
        partial.judgements[0] = partial.judgements[0].model_copy(update={"unpriced_attempts": 1})

        summary = cost_summary([complete, partial], "llm")

        assert summary.mean == pytest.approx(0.002)
        assert summary.total == pytest.approx(0.003)  # a known subtotal
        assert summary.unreported == 1

    def test_latency_percentiles_interpolate_between_calls(self) -> None:
        items = [_item(str(i), llm=[4], latency=float(i)) for i in range(1, 6)]

        summary = latency_summary(items, "llm")

        assert summary.p50 == pytest.approx(3.0)
        assert summary.p95 == pytest.approx(4.8)
