import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.decisions import DECISION_MODEL
from glean.dependencies import get_llm_router
from glean.llm import Feature
from glean.main import app
from glean.meal_plan.dietary_decisions import (
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.meal_plan.schemas import (
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanRecipe,
    MealPlanRequest,
    MealPlanResponse,
)
from glean.meal_plan.service import generate_meal_plan
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes import corpus as corpus_module
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

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


def test_generate_meal_plan_accepts_uncategorised_pantry_items(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # Pantry items added in the app get no ingredient category, so the app sends food_group: null.
    request = {**SAMPLE_REQUEST, "pantry": [{**SAMPLE_REQUEST["pantry"][0], "food_group": None}]}
    llm_router = MagicMock()
    llm_router.invoke.return_value = MealPlanResponse(suggestions=[])
    app.dependency_overrides[get_llm_router] = lambda: llm_router

    response = client.post("/meal-plan", headers=auth_headers, json=request)

    assert response.status_code == 200


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

    history = [{"recipe_id": i, "title": f"Meal {i}", "last_cooked_at": None, "food_groups": []} for i in range(1, 5)]
    request = MealPlanRequest(**{**SAMPLE_REQUEST, "recipe_history": history, "meals_per_week": 2})
    response = generate_meal_plan(request, llm_router=llm_router)

    assert len(response.suggestions) == 2
    assert [s.recipe_id for s in response.suggestions] == [1, 2]


def test_generate_meal_plan_drops_recipes_not_in_history() -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = MealPlanResponse(
        suggestions=[
            {"recipe_id": 101, "title": "Classic Beef Bolognese", "reason": "Invented.", "missing_ingredients": []},
            {"recipe_id": 3, "title": "Lentil Soup", "reason": "Saved recipe.", "missing_ingredients": []},
        ]
    )

    response = generate_meal_plan(MealPlanRequest(**SAMPLE_REQUEST), llm_router=llm_router)

    assert [s.recipe_id for s in response.suggestions] == [3]


def test_corpus_mode_offers_sampled_candidates_and_returns_external_ids(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_bolognese",
                title="Beef Bolognese",
                reason="Uses the mince.",
            )
        ]
    )

    result = generate_meal_plan(_corpus_request(), llm_router=llm_router, corpus=corpus, rng=random.Random(0))

    assert [(s.external_id, s.recipe_id, s.title) for s in result.suggestions] == [
        ("rec_bolognese", None, "Beef Bolognese")
    ]
    args, kwargs = llm_router.invoke.call_args
    assert args[0] == Feature.MEAL_PLAN_GENERATION
    assert args[1] is CorpusMealPlanResponse
    offered = json.loads(kwargs["user"])["candidates"]
    assert {candidate["external_id"] for candidate in offered} == {"rec_bolognese", "rec_salmon"}


def test_corpus_mode_drops_recipes_that_were_not_offered(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(external_id="rec_invented", title="X", reason="Invented."),
            CorpusMealPlanRecipe(external_id="rec_salmon", title="Y", reason="Offered."),
        ]
    )

    result = generate_meal_plan(
        _corpus_request(), llm_router=llm_router, corpus=_corpus(tmp_path), rng=random.Random(0)
    )

    assert [s.external_id for s in result.suggestions] == ["rec_salmon"]


def test_corpus_mode_skips_the_model_when_nothing_is_eligible(tmp_path) -> None:
    llm_router = MagicMock()
    request = _corpus_request(exclude_external_ids=["rec_bolognese", "rec_salmon"])

    result = generate_meal_plan(request, llm_router=llm_router, corpus=_corpus(tmp_path), rng=random.Random(0))

    assert result.suggestions == []
    llm_router.invoke.assert_not_called()


def test_meal_plan_endpoint_accepts_corpus_requests_without_recipe_history(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(suggestions=[])
    app.dependency_overrides[get_llm_router] = lambda: llm_router
    body = _corpus_request().model_dump(mode="json")
    del body["recipe_history"]

    with patch("glean.meal_plan.service.RecipeCorpusStore", return_value=_corpus(tmp_path)):
        response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    assert response.json() == {"suggestions": []}


class _ModelThatSuggestsEveryCorpusRecipe:
    """The meal-plan model, faked at its boundary: it ignores the filtering and recommends every recipe it was offered
    plus every id in `also` (a model inventing or remembering recipes it wasn't offered)."""

    def __init__(self, *also: str) -> None:
        self._also = also
        self.offered: list[str] = []
        self.candidates: list[dict[str, object]] = []

    def invoke(self, _feature, _schema, *, user: str, **_kwargs) -> CorpusMealPlanResponse:
        self.candidates = json.loads(user)["candidates"]
        offered = [candidate["external_id"] for candidate in self.candidates]
        self.offered = offered
        return CorpusMealPlanResponse(
            suggestions=[
                CorpusMealPlanRecipe(external_id=external_id, title=external_id, reason="Looks good.")
                for external_id in [*offered, *self._also]
            ]
        )


def test_an_older_app_build_sending_nut_free_is_never_planned_a_tree_nut_or_a_peanut_recipe(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    corpus = RecipeCorpusStore()
    recipes = {
        "rec_rice": ("Plain Rice", ["rice"], 0.02, 0.02),
        "rec_pesto": ("Pesto Pasta", ["spaghetti", "pesto"], 0.97, 0.02),
        "rec_satay": ("Satay Noodles", ["noodles", "satay sauce"], 0.02, 0.97),
    }
    for external_id, (title, ingredients, _tree, _peanut) in recipes.items():
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=external_id,
                flag=flag,
                probability=probability,
                model=f"{DECISION_MODEL}-20261014",
                content_hash=content_fingerprint(title, ingredients),
                criteria_hash=question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 16, tzinfo=UTC),
            )
            for external_id, (title, ingredients, tree, peanut) in recipes.items()
            for flag, probability in (("tree-nut-free", tree), ("peanut-free", peanut))
        ]
    )
    app.dependency_overrides[get_llm_router] = lambda: _ModelThatSuggestsEveryCorpusRecipe("rec_pesto", "rec_satay")
    body = _corpus_request(dietary_flags=["Nut-Free"]).model_dump(mode="json")
    del body["recipe_history"]

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    assert [suggestion["external_id"] for suggestion in response.json()["suggestions"]] == ["rec_rice"]


def test_corpus_mode_never_offers_a_recipe_cooked_in_the_last_six_weeks(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    _corpus_with(
        tmp_path,
        {
            "rec_bolognese": ("Beef Bolognese", ["beef mince"]),
            "rec_tacos": ("Beef Tacos", ["beef mince", "tortilla"]),
            "rec_meatballs": ("Beef Meatballs", ["beef mince", "breadcrumbs"]),
            "rec_stir_fry": ("Beef Stir Fry", ["beef mince", "noodles"]),
        },
    )
    model = _ModelThatSuggestsEveryCorpusRecipe()
    app.dependency_overrides[get_llm_router] = lambda: model
    body = _corpus_request(
        meals_per_week=1,
        cooked_history=[_cooked("rec_bolognese", "Beef Bolognese", days_ago=10)],
    ).model_dump(mode="json")

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    assert "rec_bolognese" not in model.offered
    assert set(model.offered) == {"rec_tacos", "rec_meatballs", "rec_stir_fry"}


def test_corpus_mode_relaxes_the_floor_rather_than_leave_the_week_unfillable(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    _corpus_with(
        tmp_path,
        {
            "rec_bolognese": ("Beef Bolognese", ["beef mince"]),
            "rec_tacos": ("Beef Tacos", ["beef mince", "tortilla"]),
            "rec_meatballs": ("Beef Meatballs", ["beef mince", "breadcrumbs"]),
        },
    )
    model = _ModelThatSuggestsEveryCorpusRecipe()
    app.dependency_overrides[get_llm_router] = lambda: model
    body = _corpus_request(
        meals_per_week=2,
        cooked_history=[_cooked("rec_bolognese", "Beef Bolognese", days_ago=10)],
    ).model_dump(mode="json")

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    assert set(model.offered) == {"rec_bolognese", "rec_tacos", "rec_meatballs"}


def test_a_vegetarian_household_is_never_offered_a_meat_recipe_even_when_the_floor_relaxes(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    recipes = {
        "rec_lentil_bake": ("Lentil Bake", ["lentils", "potato"], 0.02),
        "rec_chickpea_curry": ("Chickpea Curry", ["chickpeas", "coconut milk"], 0.02),
        "rec_tofu_noodles": ("Tofu Noodles", ["tofu", "noodles"], 0.02),
        "rec_chicken_pie": ("Chicken Pie", ["chicken breast", "pastry"], 0.97),
    }
    corpus = _corpus_with(
        tmp_path, {external_id: (title, ingredients) for external_id, (title, ingredients, _) in recipes.items()}
    )
    _save_decisions(
        corpus,
        [
            (external_id, "vegetarian", probability)
            for external_id, (_title, _ingredients, probability) in recipes.items()
        ],
    )
    model = _ModelThatSuggestsEveryCorpusRecipe("rec_chicken_pie")
    app.dependency_overrides[get_llm_router] = lambda: model
    body = _corpus_request(
        dietary_flags=["vegetarian"],
        meals_per_week=3,
        # Every cooked recipe here is recent, so the floor has to relax for the week to fill at all.
        cooked_history=[
            _cooked("rec_lentil_bake", "Lentil Bake", days_ago=10),
            _cooked("rec_chickpea_curry", "Chickpea Curry", days_ago=20),
            _cooked("rec_chicken_pie", "Chicken Pie", days_ago=30),
        ],
    ).model_dump(mode="json")

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    # The floor relaxed: the recently cooked vegetarian recipes came back into the candidates. The meat
    # recipe, which is just as recent but breaks the flag, never appears — not even when the model asks
    # for it by id, because the service drops anything it didn't offer.
    assert set(model.offered) == {"rec_lentil_bake", "rec_chickpea_curry", "rec_tofu_noodles"}
    assert {suggestion["external_id"] for suggestion in response.json()["suggestions"]} == {
        "rec_lentil_bake",
        "rec_chickpea_curry",
        "rec_tofu_noodles",
    }


def test_the_model_is_told_which_candidates_are_cooked_recently_and_that_fresh_ones_come_first(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    _corpus_with(
        tmp_path,
        {
            "rec_bolognese": ("Beef Bolognese", ["beef mince"]),
            "rec_tacos": ("Beef Tacos", ["beef mince", "tortilla"]),
            "rec_meatballs": ("Beef Meatballs", ["beef mince", "breadcrumbs"]),
        },
    )
    model = _ModelThatSuggestsEveryCorpusRecipe()
    app.dependency_overrides[get_llm_router] = lambda: model
    body = _corpus_request(
        meals_per_week=2,  # six fresh recipes needed, so the floor relaxes
        cooked_history=[_cooked("rec_bolognese", "Beef Bolognese", days_ago=10)],
    ).model_dump(mode="json")

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    ages = {candidate["external_id"]: candidate["cooked_days_ago"] for candidate in model.candidates}
    assert ages == {"rec_bolognese": 10, "rec_tacos": None, "rec_meatballs": None}
    assert [candidate["external_id"] for candidate in model.candidates][-1] == "rec_bolognese"


def test_cooked_history_is_a_bounded_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    app.dependency_overrides[get_llm_router] = lambda: _ModelThatSuggestsEveryCorpusRecipe()
    body = {
        **_corpus_request().model_dump(mode="json"),
        "cooked_history": [_cooked(f"rec_{index}", f"Meal {index}", days_ago=1) for index in range(201)],
    }

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 422


def test_cooked_history_entries_take_a_title_when_the_app_kept_no_recipe_id(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: FilesystemBlobStore(tmp_path))
    _corpus_with(
        tmp_path,
        {
            "rec_bolognese": ("Beef Bolognese", ["beef mince"]),
            "rec_tacos": ("Beef Tacos", ["beef mince", "tortilla"]),
            "rec_meatballs": ("Beef Meatballs", ["beef mince", "breadcrumbs"]),
            "rec_stir_fry": ("Beef Stir Fry", ["beef mince", "noodles"]),
        },
    )
    model = _ModelThatSuggestsEveryCorpusRecipe()
    app.dependency_overrides[get_llm_router] = lambda: model
    body = _corpus_request(
        meals_per_week=1,
        cooked_history=[{"recipe_id": None, "title": "Beef Bolognese", "cooked_at": _iso(days_ago=10)}],
    ).model_dump(mode="json")

    response = client.post("/meal-plan", headers=auth_headers, json=body)

    assert response.status_code == 200
    assert "rec_bolognese" not in model.offered


def _cooked(recipe_id: str, title: str, *, days_ago: float) -> dict[str, object]:
    return {"recipe_id": recipe_id, "title": title, "cooked_at": _iso(days_ago=days_ago)}


def _iso(*, days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def test_corpus_mode_names_an_urgent_pantry_item_in_the_reason(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_herby",
                title="Coriander Chicken",
                reason="Uses pantry items well.",
            )
        ]
    )
    request = _corpus_request(pantry=[_coriander()])

    result = generate_meal_plan(
        request,
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert "coriander" in result.suggestions[0].reason
    assert "goes off Thu" in result.suggestions[0].reason


def test_corpus_mode_leaves_a_reason_that_already_names_the_urgent_item(tmp_path) -> None:
    llm_router = MagicMock()
    reason = "Uses up your coriander (goes off Thu) with the chicken."
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[CorpusMealPlanRecipe(external_id="rec_herby", title="Coriander Chicken", reason=reason)]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert result.suggestions[0].reason == reason


def test_corpus_mode_tells_the_model_which_urgent_items_each_candidate_uses(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(suggestions=[])

    generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    offered = {
        candidate["external_id"]: candidate
        for candidate in json.loads(llm_router.invoke.call_args.kwargs["user"])["candidates"]
    }
    assert offered["rec_herby"]["urgent_pantry_items"] == [
        {"name": "coriander", "expires_in_days": 2, "goes_off": "Thu"}
    ]
    assert offered["rec_other"]["urgent_pantry_items"] == []


def test_corpus_mode_does_not_name_a_pantry_item_that_is_not_about_to_go_off(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(external_id="rec_herby", title="Coriander Chicken", reason="Uses pantry items.")
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander(expires_in_days=9)]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert result.suggestions[0].reason == "Uses pantry items."


def test_corpus_mode_dates_a_going_off_item_by_the_phones_local_date(tmp_path) -> None:
    # The server is still on Tuesday 23:30 UTC while the household is already on Wednesday, so two
    # calendar days left locally means Friday -- not the server's Thursday.
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_herby",
                title="Coriander Chicken",
                reason="Uses pantry items.",
            )
        ]
    )
    request = _corpus_request(pantry=[_coriander(expires_in_days=2)], local_date=date(2026, 4, 8))

    result = generate_meal_plan(
        request,
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 23, 30, tzinfo=UTC),
    )

    assert "goes off Fri" in result.suggestions[0].reason
    offered = {
        candidate["external_id"]: candidate
        for candidate in json.loads(llm_router.invoke.call_args.kwargs["user"])["candidates"]
    }
    assert offered["rec_herby"]["urgent_pantry_items"] == [
        {"name": "coriander", "expires_in_days": 2, "goes_off": "Fri"}
    ]


def test_corpus_mode_dates_an_item_by_the_server_date_when_the_phone_sends_none(tmp_path) -> None:
    # An app build that predates the local date still gets a weekday, from the server's own date.
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(external_id="rec_herby", title="Coriander Chicken", reason="Uses pantry items.")
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander(expires_in_days=2)]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 23, 30, tzinfo=UTC),
    )

    assert "goes off Thu" in result.suggestions[0].reason


def test_a_reason_that_names_the_item_without_when_it_goes_off_gains_the_day(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(external_id="rec_herby", title="Coriander Chicken", reason="Uses up your coriander.")
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    reason = result.suggestions[0].reason
    assert "goes off Thu" in reason
    assert reason.casefold().count("coriander") == 1, reason


def test_a_reason_that_only_shares_a_word_with_the_item_is_repaired(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(external_id="rec_onion", title="Red Onion Tart", reason="A red pepper dinner.")
        ]
    )
    corpus = _corpus_with(tmp_path, {"rec_onion": ("Red Onion Tart", ["red onion"])})

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander(name="red onion")]),
        llm_router=llm_router,
        corpus=corpus,
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert "Uses up your red onion (goes off Thu)." in result.suggestions[0].reason


def test_a_reason_with_the_wrong_day_is_repaired(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_herby",
                title="Coriander Chicken",
                reason="Uses up your coriander (goes off Fri).",
            )
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    reason = result.suggestions[0].reason
    assert "goes off Thu" in reason
    assert "Fri" not in reason


def test_an_unrelated_weekday_does_not_count_as_an_expiry_claim(tmp_path) -> None:
    # "Thu dinner" is about the meal, not a claim that the coriander goes off; the wrong Friday claim
    # must still be replaced, and the dinner wording left alone.
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_herby",
                title="Coriander Chicken",
                reason="For Thu dinner, uses coriander (goes off Fri).",
            )
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    reason = result.suggestions[0].reason
    assert "goes off Thu" in reason
    assert "Fri" not in reason
    assert "For Thu dinner" in reason


def test_a_reason_naming_the_item_without_an_expiry_claim_gains_one(tmp_path) -> None:
    # A weekday in the prose is not an expiry claim, so this reason is not compliant.
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[
            CorpusMealPlanRecipe(
                external_id="rec_herby",
                title="Coriander Chicken",
                reason="Coriander is lovely for Thursday dinner.",
            )
        ]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert "goes off Thu" in result.suggestions[0].reason


def test_a_correct_full_weekday_claim_is_left_alone(tmp_path) -> None:
    llm_router = MagicMock()
    reason = "Uses up your coriander, which goes off Thursday."
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[CorpusMealPlanRecipe(external_id="rec_herby", title="Coriander Chicken", reason=reason)]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander()]),
        llm_router=llm_router,
        corpus=_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert result.suggestions[0].reason == reason


def test_a_second_urgent_item_is_not_added_when_one_is_already_named(tmp_path) -> None:
    llm_router = MagicMock()
    reason = "Uses up your lime (goes off Wed) with the coriander."
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[CorpusMealPlanRecipe(external_id="rec_both", title="Coriander Lime Chicken", reason=reason)]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander(), _coriander(name="lime", expires_in_days=1)]),
        llm_router=llm_router,
        corpus=_two_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    assert result.suggestions[0].reason == reason


def test_one_clause_is_added_when_no_urgent_item_is_named(tmp_path) -> None:
    llm_router = MagicMock()
    llm_router.invoke.return_value = CorpusMealPlanResponse(
        suggestions=[CorpusMealPlanRecipe(external_id="rec_both", title="Coriander Lime Chicken", reason="Dinner.")]
    )

    result = generate_meal_plan(
        _corpus_request(pantry=[_coriander(), _coriander(name="lime", expires_in_days=1)]),
        llm_router=llm_router,
        corpus=_two_urgent_corpus(tmp_path),
        rng=random.Random(0),
        now=datetime(2026, 4, 7, 12, tzinfo=UTC),
    )

    reason = result.suggestions[0].reason
    assert reason.count("Uses up your") == 1, reason
    assert "lime" in reason, reason
    assert "goes off Wed" in reason, reason


def _two_urgent_corpus(tmp_path) -> RecipeCorpusStore:
    return _corpus_with(tmp_path, {"rec_both": ("Coriander Lime Chicken", ["chicken", "coriander", "lime"])})


def _coriander(**overrides: object) -> dict[str, object]:
    return {
        "id": 4,
        "name": "coriander",
        "quantity": 50,
        "unit": "g",
        "food_group": "herbs",
        "urgency_score": 150.0,
        "expires_in_days": 2,
        **overrides,
    }


def _urgent_corpus(tmp_path) -> RecipeCorpusStore:
    return _corpus_with(
        tmp_path,
        {
            "rec_herby": ("Coriander Chicken", ["chicken", "coriander"]),
            "rec_other": ("Rice Bowl", ["rice"]),
        },
    )


def _corpus_with(tmp_path, recipes: dict[str, tuple[str, list[str]]]) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, (title, ingredients) in recipes.items():
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    return corpus


def _save_decisions(corpus: RecipeCorpusStore, decisions: list[tuple[str, str, float]]) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=external_id,
                flag=flag,
                probability=probability,
                model=f"{DECISION_MODEL}-20261014",
                content_hash=content_fingerprint(corpus.get(external_id).title, _ingredient_names(corpus, external_id)),
                criteria_hash=question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 16, tzinfo=UTC),
            )
            for external_id, flag, probability in decisions
        ]
    )


def _ingredient_names(corpus: RecipeCorpusStore, external_id: str) -> list[str]:
    recipe = corpus.get(external_id)
    assert recipe is not None
    return [ingredient.canonical_name for ingredient in recipe.ingredients]


def _corpus_request(**overrides: object) -> MealPlanRequest:
    return MealPlanRequest(
        **{
            **SAMPLE_REQUEST,
            "source": "corpus",
            "recipe_history": [],
            "pantry": [{**SAMPLE_REQUEST["pantry"][0], "name": "mince", "food_group": None}],
            **overrides,
        }
    )


def _corpus(tmp_path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title, ingredient in [
        ("rec_bolognese", "Beef Bolognese", "beef mince"),
        ("rec_salmon", "Salmon Teriyaki", "salmon fillet"),
    ]:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=ingredient, quantity=1, unit="each")],
            )
        )
    return corpus
