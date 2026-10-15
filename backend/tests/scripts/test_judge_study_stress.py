from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.features import FEATURES
from judge_study.results import OutputItem
from judge_study.stress import stress_variant

RECEIPT = {
    "raw_name": "WHL MILK 2L",
    "normalised_name": "whole milk",
    "quantity": 2000,
    "unit": "ml",
    "unit_price": 0.000675,
}
INPUTS: dict[str, dict[str, Any]] = {
    "receipt_scan": RECEIPT,
    "meal_plan": {
        "pantry_summary": "- rice: 800g",
        "dietary_flags": ["vegan"],
        "title": "Rice bowl",
        "reason": "Uses the rice before it expires",
    },
    "recipe_import": {
        "html_snippet": "<h1>Soup</h1>",
        "extracted_json": {
            "title": "Soup",
            "ingredients": ["water", "salt", "leek", "stock"],
            "instructions": ["Boil"],
        },
    },
    "pantry_description": {
        "purchase_text": "milk and eggs",
        "parsed_items": [{"name": "milk", "quantity": 1000, "unit": "ml"}, {"name": "eggs", "quantity": 6}],
    },
    "shopping_list_description": {
        "shopping_text": "milk and eggs",
        "parsed_response": {"items": [{"name": "milk"}, {"name": "eggs"}], "clarifying_questions": []},
    },
}


def _item(feature: str, n: int = 0) -> OutputItem:
    return OutputItem(
        item_id=f"{feature}/0/{n}",
        feature=feature,
        input={"seen": "by the feature"},
        output={"what": "it produced"},
        judge_inputs=INPUTS[feature],
    )


@pytest.mark.parametrize("feature", FEATURES)
class TestStressVariant:
    def test_it_is_a_marked_degraded_copy_judged_on_the_same_input(self, feature: str) -> None:
        source = _item(feature)

        variant = stress_variant(source)

        assert variant.origin == "stress"
        assert variant.item_id == f"{source.item_id}+stress"
        assert variant.feature == feature
        assert variant.input == source.input
        assert variant.judge_inputs != source.judge_inputs
        assert source.origin == "production"

    def test_it_can_still_be_rendered_by_the_features_judge_prompt(self, feature: str) -> None:
        assert FEATURES[feature].prompt(**stress_variant(_item(feature)).judge_inputs)

    def test_it_is_deterministic_and_leaves_the_source_untouched(self, feature: str) -> None:
        source = _item(feature)

        assert stress_variant(source) == stress_variant(source)
        assert source.judge_inputs == INPUTS[feature]

    def test_its_displayed_output_matches_what_the_judges_are_shown(self, feature: str) -> None:
        variant = stress_variant(_item(feature, 1))

        assert variant.output != _item(feature, 1).output


def test_neighbouring_outputs_are_degraded_to_different_severities() -> None:
    mild = stress_variant(_item("receipt_scan", 0)).judge_inputs
    severe = stress_variant(_item("receipt_scan", 1)).judge_inputs

    assert mild["normalised_name"] == "whole milk"  # wrong quantity and unit, right name
    assert severe["normalised_name"] != "whole milk"  # wrong item entirely
