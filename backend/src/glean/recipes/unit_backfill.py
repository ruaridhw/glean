"""One-off backfill: re-parse corpus ingredients that leaked a unit word into their name (#120).

Before the parser knew cups, ounces, sticks and vague measures, "1/4 cup butter" was stored as 0.25 pcs
"Cup butter". Re-parsing those rows with the current parser fixes them. Only the recipe corpus is touched:
the recipe-api HTTP cache holds raw API payloads, whose quantities pass through unchanged by design.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.ingredient_parser import has_trailing_size, parse_ingredient_text

if TYPE_CHECKING:
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.stored import StoredIngredient, StoredRecipe


@dataclass(frozen=True)
class UnitBackfillResult:
    recipes_scanned: int
    recipes_changed: int
    ingredients_changed: int


def backfill_unit_words(
    corpus: RecipeCorpusStore, *, dry_run: bool = True, allow_remote_store: bool = False
) -> UnitBackfillResult:
    """Re-parse `pcs` ingredients that leaked a unit word into their name. Idempotent.

    Dry run unless told otherwise, and local filesystem corpora only: a remote (S3) store is refused before
    anything is read unless the caller opts in with `allow_remote_store`.
    """
    if not allow_remote_store and not isinstance(corpus.store, FilesystemBlobStore):
        raise ValueError("unit backfill only runs against a filesystem corpus; pass allow_remote_store to override")
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
    if ingredient.unit != "pcs" or _is_clove_ingredient(ingredient.canonical_name):
        return ingredient
    # "2 cheddar (8 oz)" and "Cheddar (8 oz) x2" were stored alike but total different weights: don't guess.
    if ingredient.quantity != 1 and has_trailing_size(ingredient.canonical_name):
        return ingredient
    parsed = parse_ingredient_text(f"{float(ingredient.quantity)!r} {ingredient.canonical_name}")
    # Never trade a leaked unit word for a dirty name: leave the row alone instead.
    if (
        parsed is None
        or re.match(r"\s*\d", parsed.canonical_name)
        or (parsed.canonical_name, parsed.unit) == (ingredient.canonical_name, ingredient.unit)
    ):
        return ingredient
    return ingredient.model_copy(
        update={
            "canonical_name": parsed.canonical_name,
            "quantity": parsed.quantity,
            "unit": parsed.unit,
            "preparation": parsed.preparation or ingredient.preparation,
        }
    )


def _is_clove_ingredient(name: str) -> bool:
    """A name led by "clove" is only a clove *measure* when it is "clove of ..." or cloves of garlic.

    Otherwise it is a plain ingredient such as "Clove oil", which a re-parse would turn into "Oil".
    """
    match = re.match(r"cloves?\b\s*(?P<rest>.*)$", name.strip(), flags=re.IGNORECASE)
    if match is None:
        return False
    rest = match.group("rest").lower()
    return not (rest.startswith("of ") or "garlic" in rest)


def _with_ingredients(recipe: StoredRecipe, ingredients: list[StoredIngredient]) -> StoredRecipe:
    return recipe.model_copy(update={"ingredients": ingredients})
