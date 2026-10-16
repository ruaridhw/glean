from __future__ import annotations

from typing import Any

import pytest
from tests.integration.evals.judges import rubrics
from tests.scripts.golden_judge_prompts import GOLDEN, LONG_HTML


class _CapturingModel:
    """Stands in for the judge's chat model, the system boundary, and records what it is asked."""

    def __init__(self) -> None:
        self.messages: list[Any] = []

    def with_structured_output(self, schema: type, **_: Any) -> _CapturingModel:
        self._schema = schema
        return self

    def invoke(self, messages: list[Any], **_: Any) -> Any:
        self.messages = messages
        return self._schema(score=3)


CASES: dict[str, tuple[Any, dict[str, Any]]] = {
    "receipt scan": (
        rubrics.judge_receipt_scan,
        {
            "raw_name": "WHL MILK 2L",
            "normalised_name": "whole milk",
            "quantity": 2000,
            "unit": "ml",
            "unit_price": 0.000675,
        },
    ),
    "receipt scan without a price": (
        rubrics.judge_receipt_scan,
        {
            "raw_name": "BNLS CHKN BRST 500G",
            "normalised_name": "chicken breast",
            "quantity": 500,
            "unit": "g",
            "unit_price": None,
        },
    ),
    "meal plan": (
        rubrics.judge_meal_plan_recipe,
        {
            "pantry_summary": "- rice: 800g (urgency: 10.0)\n- spinach: 100g (urgency: 80.0)",
            "dietary_flags": ["vegan", "nut-free"],
            "title": "Spinach rice",
            "reason": "Uses the spinach that expires first",
        },
    ),
    "recipe import": (
        rubrics.judge_recipe_import,
        {
            "html_snippet": "<h1>Crème brûlée</h1>",
            "extracted_json": {"title": "Crème brûlée", "ingredients": ["cream", "sugar"], "total_time": None},
        },
    ),
    "recipe import with long html": (
        rubrics.judge_recipe_import,
        {"html_snippet": LONG_HTML, "extracted_json": {"title": "Stew"}},
    ),
    "pantry description": (
        rubrics.judge_purchase_description,
        {
            "purchase_text": "2 eggs and some milk",
            "parsed_items": [{"name": "eggs", "quantity": 2.0, "unit": "units"}, {"name": "milk", "quantity": None}],
        },
    ),
    "shopping-list description": (
        rubrics.judge_shopping_list_description,
        {
            "shopping_text": "taco shells, limes",
            "parsed_response": {"items": [{"name": "taco shells"}], "clarifying_questions": []},
        },
    ),
}


@pytest.mark.parametrize("name", CASES)
def test_each_judge_still_sends_the_exact_system_and_human_messages_it_sent_before_the_refactor(name: str) -> None:
    judge, inputs = CASES[name]
    model = _CapturingModel()

    judge(model, **inputs)

    assert [(type(message).__name__, message.content) for message in model.messages] == GOLDEN[name]


def test_the_long_html_case_really_crosses_the_2000_character_truncation() -> None:
    sent = GOLDEN["recipe import with long html"][1][1]

    assert len(LONG_HTML) > 2000
    assert LONG_HTML[:2000] in sent
    assert LONG_HTML[2000:2050] not in sent
