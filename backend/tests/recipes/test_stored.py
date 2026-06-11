from __future__ import annotations

import pytest

from glean.recipe_api.schemas import RecipeApiRecipe
from glean.recipes.stored import (
    RecipeImportError,
    RecipeParseResult,
    stored_from_llm_json,
    stored_from_recipe_api,
    stored_from_schema_org,
    stored_to_recipe_out,
)


def test_recipe_api_mapping_preserves_recipe_fields() -> None:
    api_recipe = RecipeApiRecipe(
        id="abc-123",
        name="Spaghetti Carbonara",
        cuisine="Italian",
        difficulty="Easy",
        dietary={"flags": ["high-protein"], "not_suitable_for": ["vegan"]},
        meta={"active_time": "PT15M", "total_time": "PT30M", "yield_count": 2},
        nutrition={"per_serving": {"calories": 487.22, "protein_g": 35.75}},
        ingredients=[
            {
                "group_name": "Pasta",
                "items": [
                    {
                        "ingredient_id": "spaghetti",
                        "name": "spaghetti",
                        "quantity": 200,
                        "unit": "g",
                    }
                ],
            }
        ],
        instructions=[
            {"step_number": 1, "phase": "main", "text": "Boil spaghetti."},
            {"step_number": 2, "phase": "main", "text": "Toss with sauce."},
        ],
        source_url="https://example.com/carbonara",
    )

    recipe = stored_from_recipe_api(api_recipe)
    recipe_out = stored_to_recipe_out(recipe)

    assert recipe.external_id == "recipeapi:abc-123"
    assert recipe.provider == "recipeapi"
    assert recipe.title == "Spaghetti Carbonara"
    assert recipe.source_url == "https://example.com/carbonara"
    assert recipe.dietary_flags == ["high-protein"]
    assert recipe.not_suitable_for == ["vegan"]
    assert recipe.nutrition.calories == pytest.approx(487.22)
    assert recipe.nutrition.protein_g == pytest.approx(35.75)
    assert recipe.ingredients[0].quantity == pytest.approx(200)
    assert recipe.ingredients[0].unit == "g"
    assert recipe.ingredients[0].canonical_name == "spaghetti"
    assert [instruction.text for instruction in recipe.instructions] == ["Boil spaghetti.", "Toss with sauce."]
    assert recipe_out.external_id == "recipeapi:abc-123"
    assert recipe_out.title == "Spaghetti Carbonara"
    assert recipe_out.ingredients[0].api_ingredient_id == "recipeapi:spaghetti"
    assert recipe_out.ingredients[0].canonical_name == "spaghetti"


def test_recipe_api_adapter_tolerates_partial_upstream_recipe_data() -> None:
    api_recipe = RecipeApiRecipe(
        id="partial-123",
        name="Partial Recipe",
        ingredients=[],
        instructions=[],
    )

    recipe = stored_from_recipe_api(api_recipe)

    assert recipe.external_id == "recipeapi:partial-123"
    assert recipe.ingredients == []
    assert recipe.instructions == []


def test_schema_org_conversion_handles_instruction_and_ingredient_shapes() -> None:
    recipe = stored_from_schema_org(
        {
            "name": "Tomato Soup",
            "recipeCuisine": "British",
            "totalTime": "PT40M",
            "prepTime": "PT10M",
            "recipeYield": "4 bowls",
            "recipeIngredient": ["500g tomatoes", "1 onion"],
            "recipeInstructions": [
                "Chop the vegetables.",
                {"@type": "HowToStep", "text": "Simmer until soft."},
            ],
        },
        source_url="https://example.com/tomato-soup",
        provider="schema",
    )

    assert recipe.external_id.startswith("schema:")
    assert recipe.title == "Tomato Soup"
    assert recipe.cuisine == "British"
    assert recipe.active_time_mins == 10
    assert recipe.total_time_mins == 40
    assert recipe.yield_count == 4
    assert [(ingredient.canonical_name, ingredient.quantity, ingredient.unit) for ingredient in recipe.ingredients] == [
        ("Tomatoes", 500, "g"),
        ("Onion", 1, "pcs"),
    ]
    assert [instruction.text for instruction in recipe.instructions] == [
        "Chop the vegetables.",
        "Simmer until soft.",
    ]


def test_schema_org_conversion_strips_instruction_html_entities_and_markdown() -> None:
    recipe = stored_from_schema_org(
        {
            "name": "Chicken Curry",
            "recipeIngredient": ["240 grams British Beef Mince"],
            "recipeInstructions": [
                {
                    "@type": "HowToStep",
                    "text": (
                        "<p>Bring <strong>water</strong> to the boil with "
                        "½&nbsp;tsp salt.</p><p>Stir in **carrot**.</p>"
                    ),
                },
                {"@type": "HowToStep", "text": "<ul><li>Add passata.</li><li>Simmer.</li></ul>"},
            ],
        },
        source_url="https://recipes.example.test/recipes/chicken-curry",
        provider="web",
    )

    assert [instruction.text for instruction in recipe.instructions] == [
        "Bring water to the boil with 1/2 tsp salt. Stir in carrot.",
        "Add passata. Simmer.",
    ]


def test_schema_org_conversion_strips_marketing_suffix_from_title() -> None:
    recipe = stored_from_schema_org(
        {
            "name": "Sweet Chilli Chicken Sarnie | 5 min prep | Serves 1 | Win a free Black+Blum lunch box",
            "recipeIngredient": [
                "1 unit(s) Bell Pepper",
                "240 grams British Beef Mince",
                "1 sachet(s) Central American Style Spice Mix",
            ],
            "recipeInstructions": [
                "<p>Prep <strong>the pepper</strong>&nbsp;and **spice mix**.</p>",
                "Toast the bread.",
            ],
        },
        source_url="https://recipes.example.test/recipes/sweet-chilli-chicken-sarnie",
        provider="schema",
    )

    assert recipe.title == "Sweet Chilli Chicken Sarnie"
    assert "<" not in recipe.instructions[0].text
    assert "**" not in recipe.instructions[0].text
    assert [
        (ingredient.canonical_name, ingredient.quantity, ingredient.unit) for ingredient in recipe.ingredients[:3]
    ] == [
        ("Bell Pepper", 1, "pcs"),
        ("British Beef Mince", 240, "g"),
        ("Central American Style Spice Mix", 1, "units"),
    ]


def test_schema_org_conversion_clears_implausible_total_time() -> None:
    recipe = stored_from_schema_org(
        {
            "name": "Chicken Pantry Dinner",
            "totalTime": "PT1440M",
            "recipeIngredient": [
                "1x 460g Jar Roasted Red Peppers",
                "2x 400g Can Chickpeas",
                "1x 1.4kg Whole Chicken",
            ],
            "recipeInstructions": ["Prep the ingredients.", "Cook until ready."],
        },
        source_url="https://www.recipes.example.test/recipes/chicken-pantry-dinner",
        provider="schema",
    )

    assert recipe.total_time_mins is None
    assert [
        (ingredient.canonical_name, ingredient.quantity, ingredient.unit, ingredient.preparation)
        for ingredient in recipe.ingredients
    ] == [
        ("Roasted Red Peppers", 460, "g", "1 jar"),
        ("Chickpeas", 800, "g", "2 cans"),
        ("Whole Chicken", 1400, "g", None),
    ]


def test_schema_org_recipe_without_nutrition_returns_unknown_nutrition() -> None:
    recipe = stored_from_schema_org(
        {
            "name": "Simple Pasta",
            "recipeIngredient": ["200g pasta"],
            "recipeInstructions": ["Boil pasta.", "Serve pasta."],
        },
        source_url="https://example.com/simple-pasta",
        provider="schema",
    )

    assert recipe.nutrition is None
    assert stored_to_recipe_out(recipe).nutrition is None


def test_llm_json_conversion_handles_time_yield_and_ingredient_strings() -> None:
    recipe = stored_from_llm_json(
        {
            "title": "Pasta Primavera",
            "source_url": "https://example.com/pasta",
            "cuisine": "Italian",
            "difficulty": "Easy",
            "total_time": "PT30M",
            "prep_time": "PT10M",
            "yield": "4 servings",
            "ingredients": ["200g pasta", "1 courgette"],
            "instructions": ["Boil pasta.", "Cook vegetables."],
            "dietary_flags": ["vegetarian"],
            "not_suitable_for": ["gluten-free"],
        },
        source_url="https://example.com/pasta?utm=1",
        provider="llm",
    )

    assert recipe.external_id.startswith("llm:")
    assert recipe.source_url == "https://example.com/pasta"
    assert recipe.active_time_mins == 10
    assert recipe.total_time_mins == 30
    assert recipe.yield_count == 4
    assert [ingredient.api_ingredient_id for ingredient in recipe.ingredients] == [None, None]
    assert [(ingredient.canonical_name, ingredient.quantity, ingredient.unit) for ingredient in recipe.ingredients] == [
        ("Pasta", 200, "g"),
        ("Courgette", 1, "pcs"),
    ]


def test_recipe_parse_result_allows_failed_result_without_recipe() -> None:
    result = RecipeParseResult(
        recipe=None,
        provider="schema",
        parser="schema.org",
        source_url="https://example.com/missing",
        failure_category="fetch_failed",
    )

    assert result.recipe is None
    assert result.failure_category == "fetch_failed"


@pytest.mark.parametrize(
    ("data", "expected_category"),
    [
        (
            {
                "name": " ",
                "recipeIngredient": ["1 egg"],
                "recipeInstructions": ["Crack egg.", "Cook egg."],
            },
            "missing_title",
        ),
        (
            {
                "name": "Omelette",
                "recipeIngredient": [],
                "recipeInstructions": ["Crack egg.", "Cook egg."],
            },
            "no_ingredients",
        ),
        (
            {
                "name": "Omelette",
                "recipeIngredient": ["1 egg"],
                "recipeInstructions": ["Cook egg."],
            },
            "too_few_instructions",
        ),
    ],
)
def test_validation_failures_report_exact_categories(data: dict, expected_category: str) -> None:
    with pytest.raises(RecipeImportError) as exc_info:
        stored_from_schema_org(data, source_url="https://example.com/omelette", provider="schema")

    assert exc_info.value.category == expected_category
