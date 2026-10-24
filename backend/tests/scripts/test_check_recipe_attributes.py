"""The attribute check sample: ask the model, then measure the answers against an independent labeller.

Synthetic data only (ADR 0016): the sample a test builds is written into a temp directory, exactly like the
owner's export lives outside the repo. The paid step is exercised with the fakes' HTTP-level decision client.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from scripts import check_recipe_attributes
from tests.recipes.enrichment.fakes import FakeDecisionApi

from glean.recipes.attributes import Cuisine, MainCarb, WholeFood
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

ATTRIBUTES = ("main_protein", "main_carb", "dish_type", "cuisine", "whole_food", "active_time")


def test_the_enrich_step_asks_the_model_about_the_sample_and_writes_the_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    sample = _sample(tmp_path, [("rec_one", "Synthetic Pesto Bake")])

    code = check_recipe_attributes.main(["enrich", "--sample", str(sample)], client=FakeDecisionApi().client())

    assert code == 0
    answers_path = tmp_path / "v5-check" / "answers.json"
    written = json.loads(answers_path.read_text())
    assert written["bars"] == dict.fromkeys(ATTRIBUTES, 0.7)  # the floor: the bar is chosen afterwards
    assert set(written["answers"]["rec_one"]) == set(ATTRIBUTES)
    assert written["answers"]["rec_one"]["main_protein"]["value"] == "chicken"  # the fake's top option, at 0.9
    assert written["answers"]["rec_one"]["active_time"]["value"] == "60+"
    assert "Answers:" in capsys.readouterr().out


def test_the_enrich_step_needs_the_paid_key_only_when_it_is_actually_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = _sample(tmp_path, [("rec_one", "Synthetic Pesto Bake")])
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        check_recipe_attributes.main(["enrich", "--sample", str(sample)])

    assert not (tmp_path / "v5-check" / "answers.json").exists()


def test_the_answers_file_lands_beside_the_sample_by_default(tmp_path: Path) -> None:
    sample = _sample(tmp_path, [("rec_one", "Synthetic Pesto Bake")])

    check_recipe_attributes.main(["enrich", "--sample", str(sample)], client=FakeDecisionApi().client())

    assert (tmp_path / "v5-check" / "answers.json").is_file()
    assert list(sample.glob("*.json"))  # the sample itself is never written to


def test_a_sample_that_is_not_exported_bodies_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="not a directory"):
        check_recipe_attributes.load_sample(tmp_path / "missing")

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit, match=r"holds no .* recipe bodies"):
        check_recipe_attributes.load_sample(empty)

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "rec_x.json").write_text("{not json")
    with pytest.raises(SystemExit, match="not a readable exported recipe"):
        check_recipe_attributes.load_sample(broken)


def test_the_compare_step_reports_accuracy_coverage_and_the_bar_that_earns_it(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    sample = _sample(tmp_path, [("rec_one", "Synthetic Pesto Bake")])
    _answers(
        tmp_path,
        {
            "rec_one": {
                "cuisine": {"value": "italian", "probability": 0.9},
                "main_protein": {"value": "chicken", "probability": 0.72},
            }
        },
    )
    _labels(tmp_path, {"rec_one": {"cuisine": "Italian", "main_protein": "beef", "main_carb": "rice"}})

    code = check_recipe_attributes.main(["compare", "--sample", str(sample)])

    out = capsys.readouterr().out
    assert code == 0
    assert "cuisine: 1 labelled, 1 answered" in out
    assert "main_carb: 1 labelled, 0 answered" in out  # labelled but never answered: not scored as wrong
    assert "cuisine: 0.70 - accuracy 100.0% on 1/1 labelled recipes (100% coverage)" in out  # ties go looser
    assert "main_carb: no accepted answers at any bar" in out
    assert "main_protein: 0.70 - accuracy 0.0%" in out  # 0.72 clears the floor and nothing above it
    assert "pred is what was stored" in out
    assert "Chosen bars" in out


def test_a_label_that_names_no_g1_value_is_reported_and_left_out_of_the_scoring(tmp_path: Path) -> None:
    answers = {"rec_one": {"cuisine": {"value": "italian", "probability": 0.9}}}

    comparison = check_recipe_attributes.compare_answers(
        answers, {"rec_one": {"cuisine": "Grandma's best", "main_protein": "chicken"}}
    )

    assert comparison.unreadable_labels == [("rec_one", "cuisine", "Grandma's best")]
    assert comparison.attribute("cuisine").labelled == 0
    assert comparison.attribute("main_protein").labelled == 1


def test_labels_are_normalised_in_one_place() -> None:
    assert check_recipe_attributes.normalise_label("cuisine", "Middle Eastern") == Cuisine.MIDDLE_EASTERN.value
    assert check_recipe_attributes.normalise_label("cuisine", "Thai-Inspired") == Cuisine.THAI.value
    assert check_recipe_attributes.normalise_label("main_carb", "Bread or wraps") == MainCarb.BREAD_OR_WRAPS.value
    assert check_recipe_attributes.normalise_label("whole_food", "whole") == WholeFood.WHOLE.value
    assert check_recipe_attributes.normalise_label("active_time", "15\u201330 min") == "15-30"
    assert check_recipe_attributes.normalise_label("main_protein", "unsure") == "unsure"
    assert check_recipe_attributes.normalise_label("main_protein", "mock chicken") is None


def test_an_unsure_label_carries_no_truth_and_is_not_scored() -> None:
    answers = {"rec_one": {"main_protein": {"value": "chicken", "probability": 0.9}}}

    comparison = check_recipe_attributes.compare_answers(answers, {"rec_one": {"main_protein": "unsure"}})

    assert comparison.attribute("main_protein").labelled == 0


def test_the_best_bar_prefers_accuracy_then_coverage_then_the_looser_bar() -> None:
    answers = {
        "rec_a": {"main_protein": {"value": "chicken", "probability": 0.90}},
        "rec_b": {"main_protein": {"value": "chicken", "probability": 0.88}},
        "rec_c": {"main_protein": {"value": "chicken", "probability": 0.82}},
        "rec_d": {"main_protein": {"value": "beef", "probability": 0.72}},
    }
    labels = {
        "rec_a": {"main_protein": "chicken"},
        "rec_b": {"main_protein": "chicken"},
        "rec_c": {"main_protein": "beef"},
        "rec_d": {"main_protein": "beef"},
    }

    comparison = check_recipe_attributes.compare_answers(answers, labels)
    attribute = comparison.attribute("main_protein")

    assert (attribute.at(0.8).accepted, attribute.at(0.8).accuracy) == (3, pytest.approx(2 / 3))
    assert (attribute.at(0.85).accepted, attribute.at(0.85).accuracy) == (2, 1.0)
    assert attribute.best is not None
    assert attribute.best.bar == 0.85
    assert attribute.unsure == 0


def test_an_unsure_answer_is_counted_as_unsure_and_accepted_by_no_bar() -> None:
    answers = {"rec_a": {"cuisine": {"value": "unsure", "probability": 0.6}}}

    comparison = check_recipe_attributes.compare_answers(answers, {"rec_a": {"cuisine": "thai"}})
    attribute = comparison.attribute("cuisine")

    assert (attribute.answered, attribute.unsure) == (1, 1)
    assert all(result.accepted == 0 for result in attribute.bars)
    assert attribute.best is not None
    assert attribute.best.accepted == 0


def test_a_recipe_the_labels_do_not_cover_is_never_scored() -> None:
    answers = {"rec_a": {"cuisine": {"value": "thai", "probability": 0.95}}, "rec_b": {"cuisine": {"value": "thai"}}}

    comparison = check_recipe_attributes.compare_answers(answers, {"rec_a": {"cuisine": "thai"}})

    assert comparison.attribute("cuisine").labelled == 1
    assert comparison.attribute("cuisine").confused[("thai", "thai")] == 1


def test_a_report_is_written_where_asked(tmp_path: Path) -> None:
    sample = _sample(tmp_path, [("rec_one", "Synthetic Pesto Bake")])
    _answers(tmp_path, {"rec_one": {"cuisine": {"value": "italian", "probability": 0.9}}})
    _labels(tmp_path, {"rec_one": {"cuisine": "Italian"}})
    report = tmp_path / "report.md"

    check_recipe_attributes.main(["compare", "--sample", str(sample), "--report", str(report)])

    assert "cuisine: 1 labelled, 1 answered" in report.read_text()


def _sample(tmp_path: Path, recipes: list[tuple[str, str]]) -> Path:
    """A local sample directory of exported recipe bodies, like the owner's, outside the repo's data."""
    sample = tmp_path / "v5-sample"
    sample.mkdir(parents=True)
    for external_id, title in recipes:
        recipe = StoredRecipe(
            external_id=external_id,
            title=title,
            total_time_mins=40,
            prep_time_mins=10,
            ingredients=[StoredIngredient(canonical_name="basil pesto", quantity=1, unit="each")],
        )
        (sample / f"{external_id}.json").write_text(recipe.model_dump_json(indent=2))
    return sample


def _answers(tmp_path: Path, answers: dict) -> None:
    path = tmp_path / "v5-check" / "answers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sample": str(tmp_path / "v5-sample"), "answers": answers}))


def _labels(tmp_path: Path, labels: dict) -> None:
    path = tmp_path / "v5-check" / "opus-labels.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(labels))
