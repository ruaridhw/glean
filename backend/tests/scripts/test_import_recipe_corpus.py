from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn
from unittest.mock import MagicMock

from scripts import import_recipe_corpus

from glean.recipes.stored import (
    RecipeParseResult,
    StoredIngredient,
    StoredInstruction,
    StoredRecipe,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_read_jobs_file_supports_provider_name_and_optional_url(tmp_path: Path) -> None:
    jobs_file = tmp_path / "jobs.csv"
    jobs_file.write_text(
        "provider,name,url\n"
        "web,Malaysian Coconut Chicken Pickled Cucumber,\n"
        "web,One Pan Thai Green Style Veggie Noodle Soup,\n"
        "generic,Chicken Enchiladas with Creamy Green Chile Sauce,"
        "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/"
    )

    jobs = import_recipe_corpus.read_jobs_file(jobs_file)

    assert [(job.provider, job.name, job.url) for job in jobs] == [
        ("web", "Malaysian Coconut Chicken Pickled Cucumber", None),
        ("web", "One Pan Thai Green Style Veggie Noodle Soup", None),
        (
            "generic",
            "Chicken Enchiladas with Creamy Green Chile Sauce",
            "https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/",
        ),
    ]


def test_run_jobs_imports_direct_url_and_saves_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    corpus = MagicMock()
    corpus.get_by_source_url.return_value = None
    corpus.save.side_effect = lambda recipe: recipe
    recipe = _recipe(
        provider="generic",
        external_id="generic:enchiladas",
        source_url="https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/",
    )
    monkeypatch.setattr(
        import_recipe_corpus,
        "import_url_to_canonical",
        lambda url, *, model, registry: RecipeParseResult(
            recipe=recipe,
            provider="generic",
            parser="schema.org",
            source_url=url,
        ),
    )

    results = import_recipe_corpus.run_jobs(
        [
            import_recipe_corpus.CorpusImportJob(
                provider="generic",
                name="Chicken Enchiladas with Creamy Green Chile Sauce",
                url="https://www.allrecipes.com/recipe/125658/chicken-enchiladas-with-creamy-green-chile-sauce/",
            )
        ],
        model=object(),
        corpus=corpus,
        registry=MagicMock(),
        manifest_path=tmp_path / "manifest.jsonl",
        rate_limit_seconds=0.0,
    )

    assert len(results) == 1
    assert results[0].status == "imported"
    assert results[0].recipe_id == "generic:enchiladas"
    assert corpus.save.call_args.args == (recipe,)
    assert '"provider": "generic"' in (tmp_path / "manifest.jsonl").read_text()
    assert '"status": "imported"' in (tmp_path / "manifest.jsonl").read_text()


def test_run_jobs_skips_direct_url_when_manifest_entry_has_cached_recipe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_url = "https://recipes.example.test/recipes/noodle-soup-abc123"
    recipe = _recipe(provider="web", external_id="web:cached", source_url=source_url)
    corpus = _Corpus(existing_by_id={"web:cached": recipe})
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        import_recipe_corpus.RecipeNameImportResult(
            provider="web",
            name="Noodle Soup",
            status="imported",
            source_url=source_url,
            recipe_id="web:cached",
        ).model_dump_json()
        + "\n"
    )

    def unexpected_import_url_to_canonical(*_: object, **__: object) -> NoReturn:
        raise AssertionError("direct URL job should skip from manifest before importing")

    monkeypatch.setattr(import_recipe_corpus, "import_url_to_canonical", unexpected_import_url_to_canonical)

    results = import_recipe_corpus.run_jobs(
        [
            import_recipe_corpus.CorpusImportJob(
                provider="web",
                name="Updated Noodle Soup",
                url=source_url,
            )
        ],
        model=object(),
        corpus=corpus,
        registry=MagicMock(),
        manifest_path=manifest_path,
        rate_limit_seconds=0.0,
    )

    assert [(result.status, result.source_url, result.recipe_id) for result in results] == [
        ("skipped", source_url, "web:cached")
    ]
    assert corpus.saved_recipes == []
    assert manifest_path.read_text().count("\n") == 1


class _Corpus:
    def __init__(
        self,
        *,
        existing_by_id: dict[str, StoredRecipe] | None = None,
        existing_by_url: dict[str, StoredRecipe] | None = None,
    ) -> None:
        self.existing_by_id = existing_by_id or {}
        self.existing_by_url = existing_by_url or {}
        self.saved_recipes: list[StoredRecipe] = []

    def get(self, recipe_id: str) -> StoredRecipe | None:
        return self.existing_by_id.get(recipe_id)

    def get_by_source_url(self, source_url: str) -> StoredRecipe | None:
        return self.existing_by_url.get(source_url)

    def save(self, recipe: StoredRecipe) -> StoredRecipe:
        self.saved_recipes.append(recipe)
        return recipe


def _recipe(*, provider: str, external_id: str, source_url: str) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        provider=provider,
        title="Chicken Enchiladas with Creamy Green Chile Sauce",
        source_url=source_url,
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"{provider}:ingredient:1",
                canonical_name="corn tortillas",
            )
        ],
        instructions=[
            StoredInstruction(step_number=1, phase="main", text="Fill the tortillas."),
            StoredInstruction(step_number=2, phase="main", text="Bake until bubbling."),
        ],
    )
