import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.main import app

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
    mock_result = MagicMock()
    mock_result.content = json.dumps(fixture)

    with patch("glean.meal_plan.router.create_chat_model") as mock_create:
        mock_create.return_value.invoke.return_value = mock_result
        response = client.post("/meal-plan", headers=auth_headers, json=SAMPLE_REQUEST)

    assert response.status_code == 200
    planned_recipes = response.json()["suggestions"]
    assert len(planned_recipes) == 2
    assert planned_recipes[0]["title"] == "Chicken Stir Fry"
    assert "expiring" in planned_recipes[0]["reason"]
    assert planned_recipes[1]["missing_ingredients"] == []


def test_generate_meal_plan_requires_auth(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    unauthenticated = TestClient(app)
    response = unauthenticated.post("/meal-plan", json=SAMPLE_REQUEST)
    assert response.status_code == 401
    app.dependency_overrides.clear()
