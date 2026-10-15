from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.results import Judgement, OutputItem, Results


def _judgement(judge: str = "llm", repeat: int = 1, score: int = 4, **extra: object) -> Judgement:
    return Judgement.model_validate(
        {"judge": judge, "repeat": repeat, "score": score, "model": "m/x", "latency_s": 1.2, **extra}
    )


def _item(item_id: str = "meal_plan/0/1", **extra: object) -> OutputItem:
    return OutputItem.model_validate(
        {
            "item_id": item_id,
            "feature": "meal_plan",
            "input": {"pantry": "rice"},
            "output": {"title": "Rice bowl"},
            "judge_inputs": {"title": "Rice bowl"},
            **extra,
        }
    )


class TestResultsFile:
    def test_what_is_saved_loads_back_identically(self, tmp_path: Path) -> None:
        item = _item(
            judgements=[_judgement(), _judgement("decision", confidence=0.7, weighted_score=3.6, cost_usd=1e-5)]
        )
        results = Results(models={"decision": "typesafe/jev-1.14-20261014"}, items=[item])

        results.save(tmp_path / "results.json")

        assert Results.load(tmp_path / "results.json") == results

    @pytest.mark.parametrize("score", [0, 6, -1])
    def test_a_judgement_outside_the_one_to_five_scale_is_refused(self, score: int) -> None:
        with pytest.raises(ValidationError):
            _judgement(score=score)

    def test_a_human_score_outside_the_scale_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _item(human_score=7)


class TestHumanScores:
    def test_scores_from_the_scoring_page_are_attached_to_their_items(self) -> None:
        results = Results(models={}, items=[_item("a"), _item("b")])

        merged = results.with_human_scores({"b": 2})

        assert [item.human_score for item in merged.items] == [None, 2]

    def test_a_score_for_an_unknown_item_is_an_error_not_silently_dropped(self) -> None:
        with pytest.raises(KeyError, match="zzz"):
            Results(models={}, items=[_item("a")]).with_human_scores({"zzz": 3})
