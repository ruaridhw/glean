from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from tests.integration.evals.judges import rubrics


class _CapturingModel:
    """Stands in for the judge's chat model, the system boundary, and records what it is asked."""

    def __init__(self) -> None:
        self.messages: list[Any] = []

    def with_structured_output(self, schema: type, **_: Any) -> _CapturingModel:
        self._schema = schema
        return self

    def invoke(self, messages: list[Any], **_: Any) -> Any:
        self.messages = messages
        return self._schema(score=4)


CASES = {
    "receipt scan": (
        rubrics.judge_receipt_scan,
        rubrics.receipt_scan_prompt,
        {"raw_name": "WHL MILK 2L", "normalised_name": "whole milk", "quantity": 2000, "unit": "ml", "unit_price": 0.1},
    ),
    "meal plan": (
        rubrics.judge_meal_plan_recipe,
        rubrics.meal_plan_prompt,
        {"pantry_summary": "- rice", "dietary_flags": ["vegan"], "title": "Rice", "reason": "Uses the rice"},
    ),
    "recipe import": (
        rubrics.judge_recipe_import,
        rubrics.recipe_import_prompt,
        {"html_snippet": "<h1>Soup</h1>", "extracted_json": {"title": "Soup"}},
    ),
    "pantry description": (
        rubrics.judge_purchase_description,
        rubrics.purchase_description_prompt,
        {"purchase_text": "2 eggs", "parsed_items": [{"name": "eggs"}]},
    ),
    "shopping-list description": (
        rubrics.judge_shopping_list_description,
        rubrics.shopping_list_description_prompt,
        {"shopping_text": "milk", "parsed_response": {"items": []}},
    ),
}


@pytest.mark.parametrize(("judge", "prompt", "inputs"), CASES.values(), ids=CASES.keys())
def test_the_llm_judge_reads_exactly_the_text_the_decision_judge_is_given(
    judge: Any, prompt: Any, inputs: dict
) -> None:
    model = _CapturingModel()

    judge(model, **inputs)

    human = next(message for message in model.messages if isinstance(message, HumanMessage))
    assert human.content == prompt(**inputs)
