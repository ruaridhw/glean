"""One-off backfill: re-parse corpus ingredients that leaked a unit word into their name (#120).

Before the parser knew cups, ounces, sticks and vague measures, "1/4 cup butter" was stored as 0.25 pcs
"Cup butter". Re-parsing those rows with the current parser fixes them. Only the recipe corpus is touched:
the recipe-api HTTP cache holds raw API payloads, whose quantities pass through unchanged by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.recipes.ingredient_parser import parse_ingredient_text

if TYPE_CHECKING:
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.stored import StoredIngredient, StoredRecipe


@dataclass(frozen=True)
class UnitBackfillResult:
    recipes_scanned: int
    recipes_changed: int
    ingredients_changed: int


def backfill_unit_words(corpus: RecipeCorpusStore, *, dry_run: bool = False) -> UnitBackfillResult:
    """Re-parse `pcs` ingredients whose name starts with a unit word. Idempotent."""
    scanned = changed_recipes = changed_ingredients = 0
    for recipe in corpus.all_recipes():
        scanned += 1
        ingredients = [_reparsed(ingredient) for ingredient in recipe.ingredients]
        changes = sum(new is not old for new, old in zip(ingredients, recipe.ingredients, strict=True))
        if not changes:
            continue
        changed_recipes += 1
        changed_ingredients += changes
        if not dry_run:
            corpus.save(_with_ingredients(recipe, ingredients))
    return UnitBackfillResult(scanned, changed_recipes, changed_ingredients)


def _reparsed(ingredient: StoredIngredient) -> StoredIngredient:
    if ingredient.unit != "pcs":
        return ingredient
    parsed = parse_ingredient_text(f"{float(ingredient.quantity)!r} {ingredient.canonical_name}")
    if parsed is None or (parsed.canonical_name, parsed.unit) == (ingredient.canonical_name, ingredient.unit):
        return ingredient
    return ingredient.model_copy(
        update={
            "canonical_name": parsed.canonical_name,
            "quantity": parsed.quantity,
            "unit": parsed.unit,
            "preparation": parsed.preparation or ingredient.preparation,
        }
    )


def _with_ingredients(recipe: StoredRecipe, ingredients: list[StoredIngredient]) -> StoredRecipe:
    return recipe.model_copy(update={"ingredients": ingredients})
