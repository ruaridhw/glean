"""Synthetic recipe corpus data for tests (ADR 0016: no real corpus content in the public repo)."""

from __future__ import annotations

from glean.recipes.stored import RecipeProvenance, StoredIngredient, StoredInstruction, StoredRecipe


def synthetic_recipe(
    external_id: str,
    *,
    title: str,
    ingredients: list[str],
    source_url: str | None = None,
    cuisine: str | None = None,
    dietary_flags: list[str] | None = None,
    total_time_mins: int = 25,
) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title=title,
        source_url=source_url,
        cuisine=cuisine,
        difficulty="Easy",
        total_time_mins=total_time_mins,
        dietary_flags=dietary_flags or [],
        ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Prepare the ingredients."),
            StoredInstruction(step_number=2, phase="main", text="Cook and serve."),
        ],
        provenance=RecipeProvenance(source_url=source_url or "", parser="test"),
    )


def synthetic_corpus() -> list[StoredRecipe]:
    """A handful of recipes covering search, cuisines, dietary flags and source URLs."""
    return [
        synthetic_recipe(
            "rec_tomato_pasta",
            title="Tomato Pasta",
            ingredients=["spaghetti", "tomato", "olive oil"],
            source_url="https://example.com/tomato-pasta",
            cuisine="Italian",
            dietary_flags=["Vegan"],
        ),
        synthetic_recipe(
            "rec_chicken_curry",
            title="Chicken Curry",
            ingredients=["chicken thigh", "curry paste", "coconut milk"],
            source_url="https://example.com/chicken-curry",
            cuisine="Indian",
            total_time_mins=40,
        ),
        synthetic_recipe(
            "rec_bean_tacos",
            title="Bean Tacos",
            ingredients=["black beans", "tortillas", "lime"],
            source_url="https://example.com/bean-tacos",
            cuisine="Mexican",
            dietary_flags=["Vegan", "Gluten-Free"],
            total_time_mins=20,
        ),
    ]
