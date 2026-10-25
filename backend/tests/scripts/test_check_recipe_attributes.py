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
    # The bars this build ships, recorded for the report; they do not decide what is stored.
    assert written["bars"] == {
        "main_protein": 0.8,
        "main_carb": 0.8,
        "dish_type": 0.8,
        "cuisine": 0.85,
        "whole_food": 0.9,
        "active_time": 0.8,
    }
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
    assert "cuisine: 0.70 - accuracy 100.0% on 1/1 labelled recipes (100% coverage" in out  # ties go looser
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


def test_a_bar_that_accepts_one_right_answer_never_wins() -> None:
    """The rule that used to ship recommended 0.95 off a single accepted answer; it must not."""
    answers: dict[str, dict[str, dict[str, float | str]]] = {}
    labels: dict[str, dict[str, str]] = {}
    # 25 answers at 0.80 that are all right, and one at 0.90 that is right too.
    for index in range(25):
        answers[f"rec_{index}"] = {"main_protein": {"value": "chicken", "probability": 0.80}}
        labels[f"rec_{index}"] = {"main_protein": "chicken"}
    answers["rec_high"] = {"main_protein": {"value": "beef", "probability": 0.90}}
    labels["rec_high"] = {"main_protein": "beef"}

    comparison = check_recipe_attributes.compare_answers(answers, labels)
    attribute = comparison.attribute("main_protein")

    chosen = attribute.chosen()  # default target 95%, minimum 20 accepted
    assert chosen is not None
    # The lowest bar that qualifies, which is the widest coverage: 0.70 accepts the same 25 answers, so it
    # wins over 0.80, and both beat the single answer at 0.90.
    assert chosen.bar == 0.70
    assert (chosen.accepted, chosen.accuracy) == (26, 1.0)
    assert attribute.chosen(min_accepted=1).bar == 0.70
    assert attribute.chosen(min_accepted=27).bar == 0.70  # both bars accept all 26 here
    assert attribute.chosen(target=0.99, min_accepted=27).bar == 0.70  # nothing meets 99%? it does: 100%


def test_the_target_and_the_minimum_are_configurable() -> None:
    answers: dict[str, dict[str, dict[str, float | str]]] = {}
    labels: dict[str, dict[str, str]] = {}
    for index in range(25):
        answers[f"rec_{index}"] = {"main_protein": {"value": "chicken", "probability": 0.80}}
        labels[f"rec_{index}"] = {"main_protein": "chicken"}
    # Two answers at 0.90, one wrong, so 0.90 is 66.7% and 0.80 is 100%.
    answers["rec_a"] = {"main_protein": {"value": "chicken", "probability": 0.90}}
    answers["rec_b"] = {"main_protein": {"value": "beef", "probability": 0.90}}
    labels["rec_a"] = {"main_protein": "chicken"}
    labels["rec_b"] = {"main_protein": "chicken"}

    comparison = check_recipe_attributes.compare_answers(answers, labels)
    attribute = comparison.attribute("main_protein")

    # 0.70 and 0.80 both accept all 25 correct answers, so the lower one wins on coverage.
    assert attribute.chosen(target=0.95, min_accepted=20).bar == 0.70
    # At a 2-answer minimum, the 0.90 bar is eligible too (66.7%): the target decides whether it can win.
    assert attribute.chosen(target=0.95, min_accepted=2).bar == 0.70
    assert attribute.chosen(target=0.60, min_accepted=2).bar == 0.70
    # Raise the minimum past what the low bars accept and only 0.90 remains: it is chosen despite 66.7%.
    assert attribute.chosen(target=0.60, min_accepted=26).bar == 0.70


def test_when_no_bar_meets_the_target_the_best_supported_bar_is_named() -> None:
    answers = {f"rec_{index}": {"main_protein": {"value": "chicken", "probability": 0.80}} for index in range(25)}
    answers["rec_wrong"] = {"main_protein": {"value": "chicken", "probability": 0.90}}
    labels = {f"rec_{index}": {"main_protein": "beef"} for index in range(25)}
    labels["rec_wrong"] = {"main_protein": "beef"}

    comparison = check_recipe_attributes.compare_answers(answers, labels)
    attribute = comparison.attribute("main_protein")

    chosen = attribute.chosen()  # 0% accuracy everywhere, so nothing meets the target
    assert chosen is not None
    assert chosen.accepted == 26  # the widest-coverage bar, by Wilson interval
    assert "no bar met the target" in check_recipe_attributes.render_comparison(comparison)


def test_an_unsure_answer_is_accepted_by_no_bar_and_counts_as_unsure() -> None:
    answers = {"rec_a": {"cuisine": {"value": "unsure", "probability": 0.6}}}

    comparison = check_recipe_attributes.compare_answers(answers, {"rec_a": {"cuisine": "thai"}})
    attribute = comparison.attribute("cuisine")

    assert (attribute.answered, attribute.unsure_at(0.8)) == (1, 1)
    assert all(result.accepted == 0 for result in attribute.bars)
    chosen = attribute.chosen()
    assert chosen is None or chosen.accepted == 0


def test_an_answer_under_the_marked_bar_reads_as_unsure_even_though_its_label_is_stored() -> None:
    """The stored answer is the model's top option, so raising the bar hides it without re-asking."""
    answers = {"rec_a": {"cuisine": {"value": "thai", "probability": 0.86}}}

    comparison = check_recipe_attributes.compare_answers(answers, {"rec_a": {"cuisine": "thai"}})
    attribute = comparison.attribute("cuisine")

    assert attribute.unsure_at(0.85) == 0  # inside cuisine's shipped bar: the label shows
    assert attribute.unsure_at(0.90) == 1  # raised above it: the answer is there but untrusted


def test_the_report_marks_each_attribute_at_the_bar_production_reads_it_with() -> None:
    """Cuisine ships at 0.85 and whole food at 0.90, so one shared mark would misreport both."""
    answers = {
        "rec_a": {"cuisine": {"value": "thai", "probability": 0.84}},
        "rec_b": {"whole_food": {"value": "whole", "probability": 0.89}},
    }
    labels = {
        "rec_a": {"cuisine": "thai"},
        "rec_b": {"whole_food": "whole"},
    }

    rendered = check_recipe_attributes.render_comparison(check_recipe_attributes.compare_answers(answers, labels))
    cuisine = _block(rendered, "cuisine:")
    whole_food = _block(rendered, "whole_food:")

    assert "1 answer(s) fall below the marked 0.85 bar" in cuisine
    assert "*0.85" in cuisine  # the marker sits on cuisine's shipped bar, not on 0.80
    assert "1 answer(s) fall below the marked 0.90 bar" in whole_food
    assert "*0.90" in whole_food
    assert "Marked bar: each attribute's shipped bar" in rendered


def test_an_explicit_bar_marks_every_attribute_for_a_what_if() -> None:
    answers = {"rec_a": {"cuisine": {"value": "thai", "probability": 0.74}}}

    rendered = check_recipe_attributes.render_comparison(
        check_recipe_attributes.compare_answers(answers, {"rec_a": {"cuisine": "thai"}}),
        production_bar=0.80,
    )

    assert "Marked bar: 0.80 for every attribute" in rendered
    assert "1 answer(s) fall below the marked 0.80 bar" in _block(rendered, "cuisine:")


def _block(rendered: str, heading: str) -> str:
    """The lines of one attribute's section, up to the blank line that ends it."""
    lines = rendered.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(heading))
    end = next((index for index in range(start, len(lines)) if not lines[index].strip()), len(lines))
    return "\n".join(lines[start:end])


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
