from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from glean.recipes.offline import OfflineRecipeImportJob, import_offline_recipes
from glean.recipes.stored import (
    RecipeImportError,
    RecipeParseResult,
    StoredIngredient,
    StoredInstruction,
    StoredRecipe,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_import_offline_recipes_imports_urls_saves_and_records_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _Corpus()
    recipe = _recipe(
        external_id="ab559dc41bdddf0d",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )
    import_calls: list[str] = []

    def fake_import(url: str, *, llm_router: object) -> RecipeParseResult:
        import_calls.append(url)
        return RecipeParseResult(recipe=recipe, parser="schema.org", source_url=url)

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    results = import_offline_recipes(
        [OfflineRecipeImportJob(name="Carbonara", url="https://recipes.example.test/pasta-recipes/carbonara")],
        llm_router=object(),
        corpus=corpus,
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert import_calls == ["https://recipes.example.test/pasta-recipes/carbonara"]
    assert corpus.saved_recipes == [recipe]
    assert len(results) == 1
    assert results[0].status == "imported"
    assert results[0].source_url == "https://recipes.example.test/pasta-recipes/carbonara"
    assert results[0].recipe_id == "ab559dc41bdddf0d"
    manifest_entries = _read_jsonl(tmp_path / "manifest.jsonl")
    assert manifest_entries == [
        {
            "name": "Carbonara",
            "status": "imported",
            "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
            "recipe_id": "ab559dc41bdddf0d",
            "error_category": None,
            "error_message": None,
        }
    ]


def test_import_offline_recipes_skips_urls_already_imported_in_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "Carbonara",
                "status": "imported",
                "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
                "recipe_id": "ab559dc41bdddf0d",
                "error_category": None,
                "error_message": None,
            }
        )
        + "\n"
    )
    recipe = _recipe(
        external_id="ab559dc41bdddf0d",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )

    def unexpected_import(*_: object, **__: object) -> None:
        pytest.fail("already imported URL should not import")

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", unexpected_import)

    results = import_offline_recipes(
        [OfflineRecipeImportJob(name="Carbonara", url="https://recipes.example.test/pasta-recipes/carbonara")],
        llm_router=object(),
        corpus=_Corpus(existing_recipes={"ab559dc41bdddf0d": recipe}),
        manifest_path=manifest_path,
    )

    assert len(results) == 1
    assert results[0].status == "skipped"
    assert results[0].recipe_id == "ab559dc41bdddf0d"
    assert manifest_path.read_text().count("\n") == 1


def test_import_offline_recipes_reimports_manifest_entry_when_corpus_recipe_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "Carbonara",
                "status": "imported",
                "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
                "recipe_id": "ab559dc41bdddf0d",
                "error_category": None,
                "error_message": None,
            }
        )
        + "\n"
    )
    recipe = _recipe(
        external_id="ab559dc41bdddf0d",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )

    monkeypatch.setattr(
        "glean.recipes.offline.import_url_to_canonical",
        lambda url, *, llm_router: RecipeParseResult(recipe=recipe, parser="schema.org", source_url=url),
    )

    results = import_offline_recipes(
        [OfflineRecipeImportJob(name="Carbonara", url="https://recipes.example.test/pasta-recipes/carbonara")],
        llm_router=object(),
        corpus=_Corpus(),
        manifest_path=manifest_path,
    )

    assert [result.status for result in results] == ["imported"]
    assert [entry["status"] for entry in _read_jsonl(manifest_path)] == ["imported", "imported"]


def test_duplicate_url_in_same_run_skips_after_first_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import_calls: list[str] = []
    recipe = _recipe(
        external_id="ab559dc41bdddf0d",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )

    def fake_import(url: str, *, llm_router: object) -> RecipeParseResult:
        import_calls.append(url)
        return RecipeParseResult(recipe=recipe, parser="schema.org", source_url=url)

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    manifest_path = tmp_path / "manifest.jsonl"
    results = import_offline_recipes(
        [
            OfflineRecipeImportJob(name="Carbonara", url="https://recipes.example.test/pasta-recipes/carbonara"),
            OfflineRecipeImportJob(
                name="Carbonara duplicate", url="https://recipes.example.test/pasta-recipes/carbonara"
            ),
        ],
        llm_router=object(),
        corpus=_Corpus(),
        manifest_path=manifest_path,
    )

    assert [result.status for result in results] == ["imported", "skipped"]
    assert import_calls == ["https://recipes.example.test/pasta-recipes/carbonara"]
    assert manifest_path.read_text().count("\n") == 1


def test_import_error_writes_exact_category_and_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(url: str, *, llm_router: object) -> RecipeParseResult:
        raise RecipeImportError("invalid_recipe", "Recipe must include at least two instruction steps")

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    results = import_offline_recipes(
        [OfflineRecipeImportJob(name="Carbonara", url="https://recipes.example.test/pasta-recipes/carbonara")],
        llm_router=object(),
        corpus=_Corpus(),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].error_category == "invalid_recipe"
    assert results[0].error_message == "Recipe must include at least two instruction steps"
    assert _read_jsonl(tmp_path / "manifest.jsonl")[0]["error_category"] == "invalid_recipe"


def test_manifest_append_writes_one_json_object_per_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(url: str, *, llm_router: object) -> RecipeParseResult:
        raise RecipeImportError("fetch_failed", f"Failed to fetch recipe URL: {url}")

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    import_offline_recipes(
        [
            OfflineRecipeImportJob(name="Missing one", url="https://recipes.example.test/missing-one"),
            OfflineRecipeImportJob(name="Missing two", url="https://recipes.example.test/missing-two"),
        ],
        llm_router=object(),
        corpus=_Corpus(),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    lines = (tmp_path / "manifest.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["name"] for line in lines] == ["Missing one", "Missing two"]
    assert [json.loads(line)["status"] for line in lines] == ["failed", "failed"]


class _Corpus:
    def __init__(self, *, existing_recipes: dict[str, StoredRecipe] | None = None) -> None:
        self.existing_recipes = existing_recipes or {}
        self.saved_recipes: list[StoredRecipe] = []

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self.existing_recipes.get(recipe_id)

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        return next((recipe for recipe in self.existing_recipes.values() if recipe.source_url == source_url), None)

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        self.saved_recipes.append(recipe)
        self.existing_recipes[recipe.external_id] = recipe
        return recipe


def _recipe(*, external_id: str, source_url: str) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title="Chicken Enchiladas with Creamy Green Chile Sauce",
        source_url=source_url,
        ingredients=[
            StoredIngredient(
                canonical_name="corn tortillas",
            )
        ],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Fill the tortillas."),
            StoredInstruction(step_number=2, phase="main", text="Bake until bubbling."),
        ],
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]
