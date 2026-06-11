from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from glean.recipes.offline import RecipeNameImportJob, import_recipe_names
from glean.recipes.providers import FetchedPage
from glean.recipes.stored import (
    RecipeImportError,
    RecipeParseResult,
    RecipeProvenance,
    StoredIngredient,
    StoredInstruction,
    StoredRecipe,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_import_recipe_names_searches_imports_saves_and_records_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _Provider("web")
    registry = _Registry(provider)
    corpus = _Corpus()
    recipe = _recipe(
        external_id="web:carbonara",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )
    calls: list[str] = []

    def fake_fetch(url: str) -> FetchedPage:
        calls.append(url)
        return FetchedPage(url=url, text='<a href="/cookbook/pasta-recipes/carbonara">Carbonara</a>')

    monkeypatch.setattr("glean.recipes.offline.fetch_public_https", fake_fetch)
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: "https://recipes.example.test/pasta-recipes/carbonara",
    )
    monkeypatch.setattr(
        "glean.recipes.offline.import_url_to_canonical",
        lambda url, *, model, registry: RecipeParseResult(
            recipe=recipe,
            provider="web",
            parser="schema.org",
            source_url=url,
        ),
    )

    results = import_recipe_names(
        [RecipeNameImportJob(provider="web", name="Carbonara")],
        model=object(),
        corpus=corpus,
        registry=registry,
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert calls == ["https://example.com/web/search?q=Carbonara"]
    assert corpus.saved_recipes == [recipe]
    assert len(results) == 1
    assert results[0].status == "imported"
    assert results[0].source_url == "https://recipes.example.test/pasta-recipes/carbonara"
    assert results[0].recipe_id == "web:carbonara"
    manifest_entries = _read_jsonl(tmp_path / "manifest.jsonl")
    assert manifest_entries == [
        {
            "provider": "web",
            "name": "Carbonara",
            "status": "imported",
            "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
            "recipe_id": "web:carbonara",
            "error_category": None,
            "error_message": None,
        }
    ]


def test_import_recipe_names_skips_names_already_imported_in_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "web",
                "name": "Carbonara",
                "status": "imported",
                "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
                "recipe_id": "web:carbonara",
                "error_category": None,
                "error_message": None,
            }
        )
        + "\n"
    )
    recipe = _recipe(
        external_id="web:carbonara",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )
    monkeypatch.setattr(
        "glean.recipes.offline.fetch_public_https",
        lambda url: pytest.fail("already imported recipe should not fetch"),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.import_url_to_canonical",
        lambda url, *, model, registry: pytest.fail("already imported recipe should not import"),
    )

    results = import_recipe_names(
        [RecipeNameImportJob(provider="web", name="Carbonara")],
        model=object(),
        corpus=_Corpus(existing_recipes={"web:carbonara": recipe}),
        registry=_Registry(_Provider("web")),
        manifest_path=manifest_path,
    )

    assert len(results) == 1
    assert results[0].status == "skipped"
    assert manifest_path.read_text().count("\n") == 1


def test_import_recipe_names_reimports_manifest_entry_when_corpus_recipe_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "web",
                "name": "Carbonara",
                "status": "imported",
                "source_url": "https://recipes.example.test/pasta-recipes/carbonara",
                "recipe_id": "web:carbonara",
                "error_category": None,
                "error_message": None,
            }
        )
        + "\n"
    )
    fetch_calls: list[str] = []
    recipe = _recipe(
        external_id="web:carbonara",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )

    def fake_fetch(url: str) -> FetchedPage:
        fetch_calls.append(url)
        return FetchedPage(url=url, text='<a href="/cookbook/pasta-recipes/carbonara">Carbonara</a>')

    monkeypatch.setattr("glean.recipes.offline.fetch_public_https", fake_fetch)
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: "https://recipes.example.test/pasta-recipes/carbonara",
    )
    monkeypatch.setattr(
        "glean.recipes.offline.import_url_to_canonical",
        lambda url, *, model, registry: RecipeParseResult(
            recipe=recipe,
            provider="web",
            parser="schema.org",
            source_url=url,
        ),
    )

    results = import_recipe_names(
        [RecipeNameImportJob(provider="web", name="Carbonara")],
        model=object(),
        corpus=_Corpus(),
        registry=_Registry(_Provider("web")),
        manifest_path=manifest_path,
    )

    assert [result.status for result in results] == ["imported"]
    assert fetch_calls == ["https://example.com/web/search?q=Carbonara"]
    assert [entry["status"] for entry in _read_jsonl(manifest_path)] == ["imported", "imported"]


def test_duplicate_imported_name_in_same_run_skips_after_first_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch_calls: list[str] = []
    import_calls: list[str] = []
    recipe = _recipe(
        external_id="web:carbonara",
        source_url="https://recipes.example.test/pasta-recipes/carbonara",
    )

    def fake_fetch(url: str) -> FetchedPage:
        fetch_calls.append(url)
        return FetchedPage(url=url, text='<a href="/cookbook/pasta-recipes/carbonara">Carbonara</a>')

    def fake_import(url: str, *, model: object, registry: object) -> RecipeParseResult:
        import_calls.append(url)
        return RecipeParseResult(
            recipe=recipe,
            provider="web",
            parser="schema.org",
            source_url=url,
        )

    monkeypatch.setattr("glean.recipes.offline.fetch_public_https", fake_fetch)
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: "https://recipes.example.test/pasta-recipes/carbonara",
    )
    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    manifest_path = tmp_path / "manifest.jsonl"
    results = import_recipe_names(
        [
            RecipeNameImportJob(provider="web", name="Carbonara"),
            RecipeNameImportJob(provider="web", name="Carbonara"),
        ],
        model=object(),
        corpus=_Corpus(),
        registry=_Registry(_Provider("web")),
        manifest_path=manifest_path,
    )

    assert [result.status for result in results] == ["imported", "skipped"]
    assert fetch_calls == ["https://example.com/web/search?q=Carbonara"]
    assert import_calls == ["https://recipes.example.test/pasta-recipes/carbonara"]
    manifest_entries = _read_jsonl(manifest_path)
    assert len(manifest_entries) == 1
    assert manifest_entries[0]["status"] == "imported"


def test_unsupported_provider_search_scheme_fails_without_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch_calls: list[str] = []

    def fake_fetch(url: str) -> FetchedPage:
        fetch_calls.append(url)
        raise RuntimeError("fetch should not be called for unsupported search schemes")

    monkeypatch.setattr("glean.recipes.offline.fetch_public_https", fake_fetch)

    results = import_recipe_names(
        [RecipeNameImportJob(provider="recipeapi", name="Carbonara")],
        model=object(),
        corpus=_Corpus(),
        registry=_Registry(_Provider("recipeapi", search_scheme="recipeapi")),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert fetch_calls == []
    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].error_category == "unsupported_provider_search"
    assert "Provider search URL must use HTTPS" in (results[0].error_message or "")


def test_failed_search_writes_failure_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _Provider("web")
    corpus = _Corpus()
    recipe = _recipe(
        external_id="web:risotto",
        source_url="https://recipes.example.test/rice-recipes/risotto",
    )
    discovered_urls = iter([None, "https://recipes.example.test/rice-recipes/risotto"])

    monkeypatch.setattr(
        "glean.recipes.offline.fetch_public_https",
        lambda url: FetchedPage(url=url, text="<html></html>"),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: next(discovered_urls),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.import_url_to_canonical",
        lambda url, *, model, registry: RecipeParseResult(
            recipe=recipe,
            provider="web",
            parser="schema.org",
            source_url=url,
        ),
    )

    results = import_recipe_names(
        [
            RecipeNameImportJob(provider="web", name="No match"),
            RecipeNameImportJob(provider="web", name="Risotto"),
        ],
        model=object(),
        corpus=corpus,
        registry=_Registry(provider),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert [result.status for result in results] == ["failed", "imported"]
    assert results[0].error_category == "search_no_result"
    assert results[0].error_message == "No recipe result found in provider search"
    assert corpus.saved_recipes == [recipe]
    manifest_entries = _read_jsonl(tmp_path / "manifest.jsonl")
    assert [entry["status"] for entry in manifest_entries] == ["failed", "imported"]
    assert manifest_entries[0]["error_category"] == "search_no_result"


def test_recipe_import_error_writes_exact_category_and_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "glean.recipes.offline.fetch_public_https",
        lambda url: FetchedPage(url=url, text='<a href="/cookbook/pasta-recipes/carbonara">Carbonara</a>'),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: "https://recipes.example.test/pasta-recipes/carbonara",
    )

    def fake_import(url: str, *, model: object, registry: object) -> RecipeParseResult:
        raise RecipeImportError("invalid_recipe", "Recipe must include at least two instruction steps")

    monkeypatch.setattr("glean.recipes.offline.import_url_to_canonical", fake_import)

    results = import_recipe_names(
        [RecipeNameImportJob(provider="web", name="Carbonara")],
        model=object(),
        corpus=_Corpus(),
        registry=_Registry(_Provider("web")),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].error_category == "invalid_recipe"
    assert results[0].error_message == "Recipe must include at least two instruction steps"
    assert _read_jsonl(tmp_path / "manifest.jsonl")[0]["error_category"] == "invalid_recipe"


def test_manifest_append_writes_one_json_object_per_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "glean.recipes.offline.fetch_public_https",
        lambda url: FetchedPage(url=url, text="<html></html>"),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: None,
    )

    import_recipe_names(
        [
            RecipeNameImportJob(provider="web", name="Missing one"),
            RecipeNameImportJob(provider="web", name="Missing two"),
        ],
        model=object(),
        corpus=_Corpus(),
        registry=_Registry(_Provider("web")),
        manifest_path=tmp_path / "manifest.jsonl",
    )

    lines = (tmp_path / "manifest.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["name"] for line in lines] == ["Missing one", "Missing two"]
    assert [json.loads(line)["status"] for line in lines] == ["failed", "failed"]


def test_rate_limit_sleeps_only_between_non_skipped_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "web",
                "name": "Already imported",
                "status": "imported",
                "source_url": "https://recipes.example.test/imported",
                "recipe_id": "web:imported",
                "error_category": None,
                "error_message": None,
            }
        )
        + "\n"
    )
    imported_recipe = _recipe(
        external_id="web:imported",
        source_url="https://recipes.example.test/imported",
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr("glean.recipes.offline.time.sleep", sleep_calls.append)
    monkeypatch.setattr(
        "glean.recipes.offline.fetch_public_https",
        lambda url: FetchedPage(url=url, text="<html></html>"),
    )
    monkeypatch.setattr(
        "glean.recipes.offline.discover_first_recipe_url",
        lambda search_html, *, base_url, provider: None,
    )

    import_recipe_names(
        [
            RecipeNameImportJob(provider="web", name="Missing one"),
            RecipeNameImportJob(provider="web", name="Already imported"),
            RecipeNameImportJob(provider="web", name="Missing two"),
        ],
        model=object(),
        corpus=_Corpus(existing_recipes={"web:imported": imported_recipe}),
        registry=_Registry(_Provider("web")),
        manifest_path=manifest_path,
        rate_limit_seconds=0.25,
    )

    assert sleep_calls == [0.25]


@dataclass
class _Provider:
    name: str
    domains: tuple[str, ...] = ("example.com",)
    search_scheme: str = "https"

    def search_url(self, query: str) -> str:
        return f"{self.search_scheme}://example.com/{self.name}/search?q={query}"


class _Registry:
    def __init__(self, provider: _Provider) -> None:
        self.provider = provider
        self.requested_names: list[str] = []

    def provider_by_name(self, name: str) -> _Provider:
        self.requested_names.append(name)
        return self.provider


class _Corpus:
    def __init__(self, existing_recipes: dict[str, StoredRecipe] | None = None) -> None:
        self._recipes = existing_recipes or {}
        self.saved_recipes: list[StoredRecipe] = []

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        self.saved_recipes.append(recipe)
        self._recipes[recipe.external_id] = recipe
        return recipe

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self._recipes.get(recipe_id)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _recipe(*, external_id: str, source_url: str) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        provider="web",
        title="Carbonara",
        source_url=source_url,
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"{external_id}:ingredient:1",
                canonical_name="spaghetti",
                quantity=200,
                unit="g",
            )
        ],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Boil the spaghetti."),
            StoredInstruction(step_number=2, phase="main", text="Toss with the sauce."),
        ],
        provenance=RecipeProvenance(
            provider="web",
            source_url=source_url,
            parser="schema.org",
        ),
    )
