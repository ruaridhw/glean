import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router
from glean.llm import Feature
from glean.main import app
from glean.meal_plan.schemas import MealPlanRecipe, MealPlanRequest, MealPlanResponse
from glean.meal_plan.service import generate_meal_plan

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_REQUEST = {
    "pantry": [
        {
            "id": 1,
            "name": "chicken breast",
            "quantity": 400,
            "unit": "g",
            "food_group": "protein",
            "urgency_score": 85.0,
        },
    ],
    "recipe_history": [
        {
            "recipe_id": 1,
            "title": "Chicken Stir Fry",
            "last_cooked_at": "2026-03-17T00:00:00Z",
            "food_groups": ["protein", "veg"],
        },
        {
            "recipe_id": 3,
            "title": "Lentil Soup",
            "last_cooked_at": None,
            "food_groups": ["protein", "carb"],
        },
    ],
    "food_group_coverage": {"protein": 1, "carb": 2, "veg": 1},
    "purchase_tolerance": 0.3,
    "meals_per_week": 5,
    "dietary_flags": [],
    "max_active_time_mins": None,
}


def test_generate_meal_plan_returns_ranked_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    fixture = json.loads((FIXTURES / "meal_plan_claude.json").read_text())
    structured_response = MealPlanResponse(suggestions=[MealPlanRecipe(**item) for item in fixture])

    llm_router = MagicMock()
    llm_router.invoke.return_value = structured_response
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    response = client.post("/meal-plan", headers=auth_headers, json=SAMPLE_REQUEST)

    assert response.status_code == 200
    planned_recipes = response.json()["suggestions"]
    assert len(planned_recipes) == 2
    assert planned_recipes[0]["title"] == "Chicken Stir Fry"
    assert "expiring" in planned_recipes[0]["reason"]
    assert planned_recipes[1]["missing_ingredients"] == []
    args, _ = llm_router.invoke.call_args
    assert args[0] == Feature.MEAL_PLAN_GENERATION
    assert args[1] is MealPlanResponse


def test_generate_meal_plan_requires_auth(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    unauthenticated = TestClient(app)
    response = unauthenticated.post("/meal-plan", json=SAMPLE_REQUEST)
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_generate_meal_plan_uses_meal_plan_feature_metadata() -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = MealPlanResponse(
        suggestions=[
            {
                "recipe_id": 1,
                "title": "Chicken Stir Fry",
                "reason": "Uses the chicken breast already in the pantry.",
                "missing_ingredients": [],
            }
        ]
    )

    response = generate_meal_plan(MealPlanRequest(**SAMPLE_REQUEST), llm_router=llm_router)

    assert response.suggestions[0].recipe_id == 1
    args, _ = llm_router.invoke.call_args
    assert args[0] == Feature.MEAL_PLAN_GENERATION
    assert args[1] is MealPlanResponse


def test_generate_meal_plan_truncates_to_meals_per_week() -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = MealPlanResponse(
        suggestions=[
            {
                "recipe_id": i,
                "title": f"Meal {i}",
                "reason": "Uses pantry items well.",
                "missing_ingredients": [],
            }
            for i in range(1, 5)  # model returns 4 despite the limit
        ]
    )

    request = MealPlanRequest(**{**SAMPLE_REQUEST, "meals_per_week": 2})
    response = generate_meal_plan(request, llm_router=llm_router)

    assert len(response.suggestions) == 2
    assert [s.recipe_id for s in response.suggestions] == [1, 2]
