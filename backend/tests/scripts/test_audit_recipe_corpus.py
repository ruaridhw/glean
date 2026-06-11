from __future__ import annotations

import json
from typing import TYPE_CHECKING

from scripts import audit_recipe_corpus

from glean.recipes.offline import RecipeNameImportResult
from glean.recipes.stored import (
    StoredIngredient,
    StoredInstruction,
    StoredNutrition,
    StoredRecipe,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_audit_corpus_reports_quality_and_metadata_issues(tmp_path: Path) -> None:
    cache_root = tmp_path / "recipes"
    _write_jobs(
        cache_root,
        [
            ("generic", "Bad Recipe", "https://example.com/bad"),
            ("web", "Web Recipe", "https://recipes.example.test/recipes/web-recipe"),
            ("generic", "Missing Recipe", "https://example.com/missing"),
        ],
    )
    _write_manifest(
        cache_root,
        [
            RecipeNameImportResult(
                provider="generic",
                name="Bad Recipe",
                status="imported",
                source_url="https://example.com/bad",
                recipe_id="generic:bad",
            ),
            RecipeNameImportResult(
                provider="web",
                name="Web Recipe",
                status="imported",
                source_url="https://recipes.example.test/recipes/web-recipe",
                recipe_id="web:bad",
            ),
        ],
    )
    _write_recipe(
        cache_root,
        "generic",
        "bad.json",
        _recipe(
            external_id="generic:bad",
            provider="generic",
            title="Bad Recipe",
            source_url="https://example.com/bad",
            total_time_mins=1440,
            nutrition=StoredNutrition(),
            ingredients=[
                StoredIngredient(
                    api_ingredient_id="generic:ingredient:1",
                    canonical_name="240g beef mince",
                    quantity=0,
                    unit="",
                )
            ],
            instructions=[
                StoredInstruction(step_number=1, phase="main", text="<p>Prep **beef**.</p>"),
                StoredInstruction(step_number=2, phase="main", text="Cook beef."),
            ],
        ),
    )
    _write_recipe(
        cache_root,
        "web",
        "bad.json",
        _recipe(
            external_id="web:bad",
            provider="web",
            title="Web Recipe",
            source_url="https://recipes.example.test/recipes/web-recipe",
            nutrition=StoredNutrition(calories=605),
            ingredients=[
                StoredIngredient(
                    api_ingredient_id="web:ingredient:1",
                    canonical_name="Chicken breast",
                    quantity=0,
                    unit="",
                )
            ],
        ),
    )
    _write_recipe(
        cache_root,
        "generic",
        "orphan.json",
        _recipe(
            external_id="generic:orphan",
            provider="generic",
            title="Orphan Recipe",
            source_url="https://example.com/orphan",
            nutrition=None,
        ),
    )

    report = audit_recipe_corpus.audit_corpus(cache_root)

    assert sorted(issue.category for issue in report.issues) == [
        "active_job_missing_cache",
        "cache_missing_active_job",
        "ingredient_unparsed",
        "instruction_markup",
        "invalid_total_time",
        "unknown_nutrition_as_zero",
    ]
    assert report.provider_counts == {"generic": 2, "web": 1}


def test_main_returns_non_zero_when_fail_on_issues(tmp_path: Path, capsys) -> None:
    cache_root = tmp_path / "recipes"
    _write_jobs(cache_root, [("generic", "Missing Recipe", "https://example.com/missing")])
    _write_manifest(cache_root, [])

    result = audit_recipe_corpus.main(["--cache-root", str(cache_root), "--fail-on-issues"])

    assert result == 1
    assert "active_job_missing_cache" in capsys.readouterr().out


def test_audit_allows_web_store_cupboard_basics_without_quantities(tmp_path: Path) -> None:
    cache_root = tmp_path / "recipes"
    _write_jobs(cache_root, [("web", "Web Recipe", "https://recipes.example.test/recipes/web-recipe")])
    _write_manifest(
        cache_root,
        [
            RecipeNameImportResult(
                provider="web",
                name="Web Recipe",
                status="imported",
                source_url="https://recipes.example.test/recipes/web-recipe",
                recipe_id="web:basics",
            )
        ],
    )
    _write_recipe(
        cache_root,
        "web",
        "basics.json",
        _recipe(
            external_id="web:basics",
            provider="web",
            title="Web Recipe",
            source_url="https://recipes.example.test/recipes/web-recipe",
            nutrition=StoredNutrition(calories=605),
            ingredients=[
                StoredIngredient(canonical_name="Butter", quantity=0, unit=""),
                StoredIngredient(canonical_name="Sugar", quantity=0, unit=""),
                StoredIngredient(canonical_name="Vegetable oil", quantity=0, unit=""),
                StoredIngredient(canonical_name="Flour", quantity=0, unit=""),
                StoredIngredient(canonical_name="Water", quantity=0, unit=""),
                StoredIngredient(canonical_name="Milk", quantity=0, unit=""),
                StoredIngredient(canonical_name="Brown sugar", quantity=0, unit=""),
            ],
        ),
    )

    report = audit_recipe_corpus.audit_corpus(cache_root)

    assert report.issues == []


def test_audit_reports_compact_quantity_leaks_and_trademark_symbols(tmp_path: Path) -> None:
    cache_root = tmp_path / "recipes"
    _write_jobs(cache_root, [("web", "Web Recipe", "https://www.recipes.example.test/recipes/web-recipe")])
    _write_manifest(
        cache_root,
        [
            RecipeNameImportResult(
                provider="web",
                name="Web Recipe",
                status="imported",
                source_url="https://www.recipes.example.test/recipes/web-recipe",
                recipe_id="web:bad",
            )
        ],
    )
    _write_recipe(
        cache_root,
        "web",
        "bad.json",
        _recipe(
            external_id="web:bad",
            provider="web",
            title="Web Recipe",
            source_url="https://www.recipes.example.test/recipes/web-recipe",
            nutrition=StoredNutrition(calories=400),
            ingredients=[
                StoredIngredient(canonical_name="8Clove Garlic", quantity=1, unit="pcs"),
                StoredIngredient(canonical_name="Tenderstem® Broccoli", quantity=1, unit="pcs"),
            ],
        ),
    )

    report = audit_recipe_corpus.audit_corpus(cache_root)

    assert sorted(issue.category for issue in report.issues) == [
        "ingredient_compact_quantity_leak",
        "ingredient_trademark_symbol",
    ]


def _write_jobs(cache_root: Path, rows: list[tuple[str, str, str]]) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    lines = ["provider,name,url", *(f"{provider},{name},{url}" for provider, name, url in rows)]
    (cache_root / "jobs.csv").write_text("\n".join(lines) + "\n")


def _write_manifest(cache_root: Path, results: list[RecipeNameImportResult]) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.jsonl").write_text(
        "".join(json.dumps(result.model_dump(mode="json"), sort_keys=True) + "\n" for result in results)
    )


def _write_recipe(cache_root: Path, provider: str, filename: str, recipe: StoredRecipe) -> None:
    provider_dir = cache_root / "corpus" / provider
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / filename).write_text(recipe.model_dump_json(indent=2))


def _recipe(
    *,
    external_id: str,
    provider: str,
    title: str,
    source_url: str,
    nutrition: StoredNutrition | None,
    ingredients: list[StoredIngredient] | None = None,
    instructions: list[StoredInstruction] | None = None,
    total_time_mins: int | None = 30,
) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        provider=provider,
        title=title,
        source_url=source_url,
        total_time_mins=total_time_mins,
        nutrition=nutrition,
        ingredients=ingredients
        or [
            StoredIngredient(
                api_ingredient_id=f"{external_id}:ingredient:1",
                canonical_name="Pasta",
                quantity=200,
                unit="g",
            )
        ],
        instructions=instructions
        or [
            StoredInstruction(step_number=1, phase="main", text="Prep ingredients."),
            StoredInstruction(step_number=2, phase="main", text="Cook ingredients."),
        ],
    )
