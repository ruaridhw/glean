import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router
from glean.llm import Feature
from glean.main import app
from glean.suggestions.schemas import SuggestionRequest
from glean.suggestions.service import get_suggestions

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


def test_get_suggestions_returns_ranked_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    fixture = json.loads((FIXTURES / "suggestion_claude.json").read_text())
    mock_result = MagicMock()
    mock_result.content = json.dumps(fixture)

    llm_router = MagicMock()
    llm_router.chat_model.return_value.invoke.return_value = mock_result
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    response = client.post("/suggestions", headers=auth_headers, json=SAMPLE_REQUEST)

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["title"] == "Chicken Stir Fry"
    assert "expiring" in suggestions[0]["reason"]
    assert suggestions[1]["missing_ingredients"] == []
    llm_router.chat_model.assert_called_once_with(Feature.MEAL_PLAN_GENERATION)


def test_get_suggestions_requires_auth(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    unauthenticated = TestClient(app)
    response = unauthenticated.post("/suggestions", json=SAMPLE_REQUEST)
    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_get_suggestions_uses_meal_plan_feature_metadata() -> None:
    mock_result = MagicMock()
    mock_result.content = json.dumps(
        [
            {
                "recipe_id": 1,
                "title": "Chicken Stir Fry",
                "reason": "Uses the chicken breast already in the pantry.",
                "missing_ingredients": [],
            }
        ]
    )
    model = MagicMock()
    model.invoke.return_value = mock_result

    response = get_suggestions(SuggestionRequest(**SAMPLE_REQUEST), model=model)

    assert response.suggestions[0].recipe_id == 1
    model.invoke.assert_called_once()
    _, kwargs = model.invoke.call_args
    assert kwargs["config"] == {"metadata": {"feature": "meal-plan-generation"}}
