from __future__ import annotations

import json

from glean.meal_plan.schemas import MealPlanRequest
from glean.meal_plan.service import generate_meal_plan


class _ModelResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.config: dict | None = None

    def invoke(self, messages: list[object], config: dict | None = None) -> _ModelResult:
        self.config = config
        return _ModelResult(self.content)


def test_generate_meal_plan_uses_meal_plan_generation_trace_metadata() -> None:
    model = _FakeModel(
        json.dumps(
            [
                {
                    "recipe_id": 1,
                    "title": "Chicken Stir Fry",
                    "reason": "Uses urgent chicken before it expires.",
                    "missing_ingredients": [],
                }
            ]
        )
    )

    response = generate_meal_plan(
        MealPlanRequest(
            pantry=[],
            recipe_history=[],
            food_group_coverage={},
            purchase_tolerance=0.3,
            meals_per_week=1,
            dietary_flags=[],
            max_active_time_mins=None,
        ),
        model=model,
    )

    assert response.suggestions[0].title == "Chicken Stir Fry"
    assert model.config == {"metadata": {"feature": "meal-plan-generation"}}
