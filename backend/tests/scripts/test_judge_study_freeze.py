from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.features import FEATURES
from judge_study.freeze import freeze_feature

from glean.meal_plan.schemas import MealPlanRecipe, MealPlanResponse
from glean.receipts.schemas import ParsedIngredient, ScanResponse
from glean.recipes.stored import RecipeLlmResponse
from glean.shopping.schemas import ShoppingParseResponse, ShoppingProposalItem


def _ingredient(name: str) -> ParsedIngredient:
    return ParsedIngredient(name=name, quantity=500, unit="g", unit_price=0.007, confidence=0.9)


def _run(feature: str, examples: list[dict[str, Any]], responses: list[BaseModel]) -> list:
    """Freeze with the model call replaced by canned responses: the one system boundary."""
    calls = iter(responses)
    return freeze_feature(feature, examples, lambda index, example: next(calls))  # type: ignore[arg-type]


class TestFreezeFeature:
    def test_a_receipt_yields_one_output_per_line_item_paired_with_its_raw_name(self) -> None:
        examples = [{"input": {"line_items": [{"name": "BNLS CHKN BRST 500G"}, {"name": "WHL MILK 2L"}]}}]
        response = ScanResponse(items=[_ingredient("chicken breast"), _ingredient("whole milk")])

        items = _run("receipt_scan", examples, [response])

        assert [item.item_id for item in items] == ["receipt_scan/0/0", "receipt_scan/0/1"]
        assert items[1].judge_inputs == {
            "raw_name": "WHL MILK 2L",
            "normalised_name": "whole milk",
            "quantity": 500,
            "unit": "g",
            "unit_price": 0.007,
        }
        assert items[1].input == {"name": "WHL MILK 2L"}
        assert items[1].output["name"] == "whole milk"

    def test_a_meal_plan_yields_one_output_per_suggested_recipe_with_the_pantry_summary(self) -> None:
        example = {
            "input": {
                "pantry": [{"name": "rice", "quantity": 800, "unit": "g", "urgency_score": 10.0}],
                "dietary_flags": ["vegan"],
            }
        }
        response = MealPlanResponse(
            suggestions=[
                MealPlanRecipe(recipe_id=1, title="Rice bowl", reason="Uses the rice", missing_ingredients=[]),
                MealPlanRecipe(recipe_id=2, title="Pilaf", reason="Also rice", missing_ingredients=[]),
            ]
        )

        items = _run("meal_plan", [example], [response])

        assert [item.item_id for item in items] == ["meal_plan/0/0", "meal_plan/0/1"]
        assert items[0].judge_inputs == {
            "pantry_summary": "- rice: 800g (urgency: 10.0)",
            "dietary_flags": ["vegan"],
            "title": "Rice bowl",
            "reason": "Uses the rice",
        }

    def test_a_recipe_import_is_one_output_per_page(self) -> None:
        example = {"input": {"html": "<h1>Soup</h1>", "url": "https://example.test/soup"}}
        response = RecipeLlmResponse(title="Soup", ingredients=["water"], instructions=["Boil"])

        (item,) = _run("recipe_import", [example], [response])

        assert item.item_id == "recipe_import/0/0"
        assert item.judge_inputs["html_snippet"] == "<h1>Soup</h1>"
        assert item.judge_inputs["extracted_json"] == response.model_dump(by_alias=True)

    def test_a_pantry_description_is_one_output_per_text_covering_all_its_parsed_items(self) -> None:
        example = {"input": {"text": "I bought chicken and milk"}}
        response = ScanResponse(items=[_ingredient("chicken"), _ingredient("milk")])

        (item,) = _run("pantry_description", [example], [response])

        assert item.judge_inputs["purchase_text"] == "I bought chicken and milk"
        assert [parsed["name"] for parsed in item.judge_inputs["parsed_items"]] == ["chicken", "milk"]

    def test_a_shopping_list_description_is_one_output_per_text(self) -> None:
        example = {"input": {"text": "taco shells"}}
        response = ShoppingParseResponse(
            items=[ShoppingProposalItem(name="taco shells", quantity=1, unit="pack", confidence=0.9)]
        )

        (item,) = _run("shopping_list_description", [example], [response])

        assert item.judge_inputs == {"shopping_text": "taco shells", "parsed_response": response.model_dump()}

    def test_every_output_can_be_judged_by_its_features_prompt_builder(self) -> None:
        example = {"input": {"line_items": [{"name": "WHL MILK 2L"}]}}
        (item,) = _run("receipt_scan", [example], [ScanResponse(items=[_ingredient("whole milk")])])

        assert "WHL MILK 2L" in FEATURES["receipt_scan"].prompt(**item.judge_inputs)

    def test_a_receipt_with_a_different_number_of_items_than_lines_is_refused(self) -> None:
        example = {"input": {"line_items": [{"name": "A"}, {"name": "B"}]}}

        with pytest.raises(ValueError, match="2 line items"):
            _run("receipt_scan", [example], [ScanResponse(items=[_ingredient("a")])])
