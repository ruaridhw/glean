from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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

    result = backfill_unit_words(corpus, dry_run=False)

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

    result = backfill_unit_words(corpus, dry_run=False)

    assert corpus.get("import:clean") == clean
    rewritten = corpus.get("import:mixed").ingredients[0]
    assert (rewritten.canonical_name, rewritten.quantity, rewritten.unit) == ("Butter", 226.0, "g")
    assert (rewritten.api_ingredient_id, rewritten.is_optional, rewritten.substitutions) == ("a2", True, ["margarine"])
    assert (result.recipes_scanned, result.recipes_changed, result.ingredients_changed) == (2, 1, 1)


def test_backfill_is_idempotent(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    corpus.save(_recipe("import:leaky", _leaked("Cup butter", 1)))
    backfill_unit_words(corpus, dry_run=False)

    second = backfill_unit_words(corpus, dry_run=False)

    assert (second.recipes_changed, second.ingredients_changed) == (0, 0)


def test_backfill_defaults_to_a_dry_run(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    leaky = _recipe("import:leaky", _leaked("Oz cheddar", 8))
    corpus.save(leaky)

    result = backfill_unit_words(corpus)

    assert result.ingredients_changed == 1
    assert corpus.get("import:leaky") == leaky


def test_backfill_keeps_a_parenthetical_size_out_of_the_name(tmp_path: Path) -> None:
    # The old parser stored "Cheddar (8 oz)" as 1 pcs with the size left in the name.
    corpus = _corpus(tmp_path)
    corpus.save(_recipe("import:suffix", _leaked("Cheddar (8 oz)", 1)))

    backfill_unit_words(corpus, dry_run=False)

    ingredient = corpus.get("import:suffix").ingredients[0]
    assert (ingredient.canonical_name, ingredient.quantity, ingredient.unit) == ("Cheddar", pytest.approx(226.8), "g")


class _InMemoryBlobStore:
    """Stands in for a remote store such as S3; records every call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def read(self, key: str) -> str | None:
        self.calls.append(f"read {key}")

    def write(self, key: str, content: str) -> None:
        self.calls.append(f"write {key}")

    def list_keys(self, prefix: str = "") -> list[str]:
        self.calls.append("list")
        return []


def test_backfill_refuses_a_non_filesystem_store_without_touching_it() -> None:
    store = _InMemoryBlobStore()

    with pytest.raises(ValueError, match="filesystem"):
        backfill_unit_words(RecipeCorpusStore(store), dry_run=False)

    assert store.calls == []


def test_backfill_reads_a_non_filesystem_store_only_with_explicit_opt_in() -> None:
    store = _InMemoryBlobStore()

    result = backfill_unit_words(RecipeCorpusStore(store), allow_remote_store=True)

    assert result.recipes_scanned == 0
    assert store.calls == ["list"]


@pytest.mark.parametrize(
    ("stored_quantity", "expected_grams", "expected_preparation"),
    [(1, 226.8, None), (2, 453.6, "2 x 8 oz"), (3, 680.4, "3 x 8 oz")],
)
def test_backfill_multiplies_a_stored_count_by_the_parenthetical_size(
    tmp_path: Path, stored_quantity: int, expected_grams: float, expected_preparation: str | None
) -> None:
    # The old parser stored "2 cheddar (8 oz)" and "Cheddar (8 oz) x2" alike as 2 pcs "Cheddar (8 oz)".
    corpus = _corpus(tmp_path)
    corpus.save(_recipe("import:suffix", _leaked("Cheddar (8 oz)", stored_quantity)))

    backfill_unit_words(corpus, dry_run=False)

    ingredient = corpus.get("import:suffix").ingredients[0]
    assert ingredient.canonical_name == "Cheddar"
    assert ingredient.quantity == pytest.approx(expected_grams)
    assert (ingredient.unit, ingredient.preparation) == ("g", expected_preparation)


@pytest.mark.parametrize("stored_quantity", [1, 2])
@pytest.mark.parametrize("name", ["Clove oil", "Clove"])
def test_backfill_leaves_a_clove_named_ingredient_alone(tmp_path: Path, name: str, stored_quantity: int) -> None:
    corpus = _corpus(tmp_path)
    original = _recipe("import:clove", _leaked(name, stored_quantity))
    corpus.save(original)

    result = backfill_unit_words(corpus, dry_run=False)

    assert corpus.get("import:clove") == original
    assert result.ingredients_changed == 0


@pytest.mark.parametrize(("name", "quantity"), [("Clove garlic", 1), ("Cloves garlic", 3), ("Clove of garlic", 1)])
def test_backfill_still_fixes_cloves_of_garlic(tmp_path: Path, name: str, quantity: int) -> None:
    corpus = _corpus(tmp_path)
    corpus.save(_recipe("import:garlic", _leaked(name, quantity)))

    backfill_unit_words(corpus, dry_run=False)

    ingredient = corpus.get("import:garlic").ingredients[0]
    assert (ingredient.canonical_name, ingredient.quantity, ingredient.unit) == ("Garlic", quantity, "clove")


def test_backfill_leaves_a_row_untouched_rather_than_produce_a_name_that_starts_with_a_number(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    original = _recipe("import:odd", _leaked("Oz 2 tomatoes", 1))
    corpus.save(original)

    result = backfill_unit_words(corpus, dry_run=False)

    assert corpus.get("import:odd") == original
    assert result.ingredients_changed == 0
