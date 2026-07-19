from __future__ import annotations

import json

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import (
    RecipeProvenance,
    StoredIngredient,
    StoredInstruction,
    StoredRecipe,
)


def test_save_writes_json_and_loads_by_stored_id(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    recipe = _recipe(
        "import:https://example.com/carbonara",
        title="Spaghetti Carbonara",
        source_url="https://example.com/carbonara",
    )

    saved = store.save(recipe)

    assert saved == recipe
    path = tmp_path / "import" / "https%3A%2F%2Fexample.com%2Fcarbonara.json"
    assert path.exists()
    assert json.loads(path.read_text())["external_id"] == "import:https://example.com/carbonara"
    assert store.get("import:https://example.com/carbonara") == recipe


def test_save_omits_empty_imported_ingredient_ids(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    recipe = _recipe(
        "import:soup",
        title="Soup",
        source_url="https://example.com/soup",
    )
    recipe.ingredients[0].api_ingredient_id = None

    store.save(recipe)

    data = json.loads((tmp_path / "import" / "soup.json").read_text())
    assert "api_ingredient_id" not in data["ingredients"][0]
    assert store.get("import:soup") == recipe


def test_get_by_source_url_finds_recipe_saved_from_import_url(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    recipe = _recipe(
        "import:salad",
        title="Crunchy Salad",
        source_url="https://example.com/salad?utm=campaign",
    )
    store.save(recipe)

    assert store.get_by_source_url("https://example.com/salad?utm=campaign") == recipe


def test_get_returns_none_for_corrupt_json(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    namespace_dir = tmp_path / "import"
    namespace_dir.mkdir()
    (namespace_dir / "broken.json").write_text("{not valid json")

    assert store.get("import:broken") is None


def test_get_ignores_legacy_flat_recipe_files(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    recipe = _recipe("import:legacy", title="Legacy Recipe")
    (tmp_path / "import%3Alegacy.json").write_text(recipe.model_dump_json())

    assert store.get("import:legacy") is None


def test_search_returns_title_matches_in_title_order_with_total(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    store.save(_recipe("import:ziti", title="Baked Ziti", cuisine="Italian"))
    store.save(_recipe("import:carbonara", title="Spaghetti Carbonara", cuisine="Italian"))
    store.save(_recipe("import:tacos", title="Tofu Tacos", cuisine="Mexican"))

    results, total = store.search(q="A", cuisine="italian")

    assert [recipe.title for recipe in results] == ["Baked Ziti", "Spaghetti Carbonara"]
    assert total == 2


def test_search_skips_corrupt_json_files(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    recipe = _recipe("import:curry", title="Chickpea Curry", dietary_flags=["Vegan"])
    store.save(recipe)
    (tmp_path / "import" / "partial.json").write_text("{")

    results, total = store.search(q="curry")

    assert [result.title for result in results] == ["Chickpea Curry"]
    assert total == 1
    assert store.get("import:curry") == recipe


def test_search_dietary_filter_requires_all_requested_flags(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    store.save(_recipe("import:curry", title="Chickpea Curry", dietary_flags=["Vegan", "Gluten-Free"]))
    store.save(_recipe("import:salad", title="Green Salad", dietary_flags=["Vegan"]))
    store.save(_recipe("import:toast", title="Avocado Toast", dietary_flags=["Vegetarian", "Gluten-Free"]))

    results, total = store.search(dietary="vegan, gluten-free")

    assert [recipe.title for recipe in results] == ["Chickpea Curry"]
    assert total == 1


def _recipe(
    external_id: str,
    *,
    title: str,
    source_url: str | None = None,
    cuisine: str | None = None,
    dietary_flags: list[str] | None = None,
) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title=title,
        source_url=source_url,
        cuisine=cuisine,
        difficulty="Easy",
        total_time_mins=25,
        dietary_flags=dietary_flags or [],
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"{external_id}:ingredient:1",
                canonical_name="ingredient",
                quantity=1,
                unit="each",
            )
        ],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Prepare ingredients."),
            StoredInstruction(step_number=2, phase="main", text="Cook and serve."),
        ],
        provenance=RecipeProvenance(
            source_url=source_url or "",
            parser="test",
        ),
    )
