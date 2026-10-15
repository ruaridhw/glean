from __future__ import annotations

from typing import TYPE_CHECKING

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe
from glean.recipes.unit_backfill import backfill_unit_words

if TYPE_CHECKING:
    from pathlib import Path


def _recipe(external_id: str, *ingredients: StoredIngredient) -> StoredRecipe:
    return StoredRecipe(external_id=external_id, title=external_id, ingredients=list(ingredients))


def _leaked(name: str, quantity: float) -> StoredIngredient:
    return StoredIngredient(canonical_name=name, quantity=quantity, unit="pcs")


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    return RecipeCorpusStore(FilesystemBlobStore(tmp_path))


def test_backfill_reparses_pcs_ingredients_that_start_with_a_unit_word(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    corpus.save(
        _recipe(
            "import:leaky",
            _leaked("Cup butter", 0.25),
            _leaked("Oz cheddar", 8),
            _leaked("Stick butter", 1),
            _leaked("Knob butter", 1),
            _leaked("X 400g tin chopped tomatoes", 1),
            _leaked("(4 ounce) can chopped green chiles", 1),
        )
    )

    result = backfill_unit_words(corpus)

    ingredients = corpus.get("import:leaky").ingredients
    assert [(i.canonical_name, round(i.quantity, 1), i.unit, i.preparation) for i in ingredients] == [
        ("Butter", 56.7, "g", None),
        ("Cheddar", 226.8, "g", None),
        ("Butter", 113.0, "g", None),
        ("Butter", 1.0, "knob", None),
        ("Chopped tomatoes", 400.0, "g", "1 tin"),
        ("Chopped green chiles", 113.4, "g", "1 can"),
    ]
    assert (result.recipes_scanned, result.recipes_changed, result.ingredients_changed) == (1, 1, 6)


def test_backfill_leaves_clean_recipes_and_other_ingredient_fields_alone(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    clean = _recipe(
        "import:clean",
        StoredIngredient(api_ingredient_id="a1", canonical_name="Tomato", quantity=3, unit="pcs"),
        StoredIngredient(canonical_name="Plain flour", quantity=200, unit="g"),
    )
    mixed = _recipe(
        "import:mixed",
        StoredIngredient(
            api_ingredient_id="a2",
            canonical_name="Stick butter",
            quantity=2,
            unit="pcs",
            is_optional=True,
            substitutions=["margarine"],
        ),
    )
    corpus.save(clean)
    corpus.save(mixed)

    result = backfill_unit_words(corpus)

    assert corpus.get("import:clean") == clean
    rewritten = corpus.get("import:mixed").ingredients[0]
    assert (rewritten.canonical_name, rewritten.quantity, rewritten.unit) == ("Butter", 226.0, "g")
    assert (rewritten.api_ingredient_id, rewritten.is_optional, rewritten.substitutions) == ("a2", True, ["margarine"])
    assert (result.recipes_scanned, result.recipes_changed, result.ingredients_changed) == (2, 1, 1)


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    corpus.save(_recipe("import:leaky", _leaked("Cup butter", 1)))
    backfill_unit_words(corpus)

    second = backfill_unit_words(corpus)

    assert (second.recipes_changed, second.ingredients_changed) == (0, 0)


def test_dry_run_reports_changes_without_writing(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    leaky = _recipe("import:leaky", _leaked("Oz cheddar", 8))
    corpus.save(leaky)

    result = backfill_unit_words(corpus, dry_run=True)

    assert result.ingredients_changed == 1
    assert corpus.get("import:leaky") == leaky
