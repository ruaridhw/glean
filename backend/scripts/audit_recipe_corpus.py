#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

from glean.recipes.offline import RecipeNameImportResult
from glean.recipes.stored import StoredIngredient, StoredNutrition, StoredRecipe

_TRADEMARK_SYMBOL_PATTERN = re.compile(r"[®™℠©]")
_COMPACT_QUANTITY_LEAK_PATTERN = re.compile(r"^\s*\d+(?:\.\d+)?[A-Za-z]")


@dataclass(frozen=True)
class CorpusJob:
    provider: str
    name: str
    url: str | None = None


@dataclass(frozen=True)
class AuditIssue:
    category: str
    recipe_id: str | None
    detail: str


@dataclass(frozen=True)
class AuditReport:
    provider_counts: dict[str, int]
    issues: list[AuditIssue]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = audit_corpus(args.cache_root)
    print_report(report)
    return 1 if args.fail_on_issues and report.issues else 0


def audit_corpus(cache_root: Path) -> AuditReport:
    recipes = _load_recipes(cache_root)
    issues: list[AuditIssue] = []

    for recipe in recipes:
        issues.extend(_recipe_quality_issues(recipe))

    jobs = _read_jobs(cache_root / "jobs.csv")
    manifest_entries = _read_manifest(cache_root / "manifest.jsonl")
    cached_recipe_ids = {recipe.external_id for recipe in recipes}
    active_recipe_ids = _active_recipe_ids(jobs, manifest_entries, cached_recipe_ids, issues)

    issues.extend(
        AuditIssue(
            category="cache_missing_active_job",
            recipe_id=recipe.external_id,
            detail=f"Cached recipe has no active jobs.csv import: {recipe.title}",
        )
        for recipe in recipes
        if recipe.external_id not in active_recipe_ids
    )

    provider_counts: dict[str, int] = {}
    for recipe in recipes:
        provider_counts[recipe.provider] = provider_counts.get(recipe.provider, 0) + 1

    return AuditReport(provider_counts=dict(sorted(provider_counts.items())), issues=issues)


def print_report(report: AuditReport) -> None:
    print("Recipe corpus audit")
    print("Provider counts:")
    for provider, count in report.provider_counts.items():
        print(f"  {provider}: {count}")
    print(f"Issues: {len(report.issues)}")
    for issue in report.issues:
        recipe_id = issue.recipe_id or "-"
        print(f"  {issue.category}: {recipe_id}: {issue.detail}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit recipe corpus cache quality and metadata consistency.")
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--fail-on-issues", action="store_true")
    return parser.parse_args(argv)


def _load_recipes(cache_root: Path) -> list[StoredRecipe]:
    corpus_root = cache_root / "corpus"
    if not corpus_root.exists():
        return []

    recipes: list[StoredRecipe] = []
    for path in sorted(corpus_root.glob("*/*.json")):
        try:
            recipes.append(StoredRecipe.model_validate_json(path.read_text()))
        except ValueError as exc:
            recipes.append(
                StoredRecipe(
                    external_id=f"invalid:{path.relative_to(cache_root)}",
                    provider="invalid",
                    title=f"Invalid recipe JSON: {path.name}",
                    ingredients=[],
                    instructions=[],
                )
            )
            print(f"Warning: failed to parse {path}: {exc}")
    return recipes


def _recipe_quality_issues(recipe: StoredRecipe) -> list[AuditIssue]:
    return [
        *_recipe_metadata_issues(recipe),
        *_instruction_quality_issues(recipe),
        *_ingredient_quality_issues(recipe),
    ]


def _recipe_metadata_issues(recipe: StoredRecipe) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    if recipe.total_time_mins is not None and (recipe.total_time_mins <= 0 or recipe.total_time_mins >= 720):
        issues.append(
            AuditIssue(
                category="invalid_total_time",
                recipe_id=recipe.external_id,
                detail=f"total_time_mins={recipe.total_time_mins}",
            )
        )
    if _is_all_zero_nutrition(recipe.nutrition):
        issues.append(
            AuditIssue(
                category="unknown_nutrition_as_zero",
                recipe_id=recipe.external_id,
                detail="Nutrition is present but every field is zero",
            )
        )
    if _contains_trademark_symbol(recipe.title):
        issues.append(
            AuditIssue(
                category="title_trademark_symbol",
                recipe_id=recipe.external_id,
                detail=f"Title contains trademark symbol: {recipe.title}",
            )
        )

    return issues


def _instruction_quality_issues(recipe: StoredRecipe) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for instruction in recipe.instructions:
        if _contains_presentation_markup(instruction.text):
            issues.append(
                AuditIssue(
                    category="instruction_markup",
                    recipe_id=recipe.external_id,
                    detail=f"Instruction {instruction.step_number} contains markup",
                )
            )
            break
        if _contains_trademark_symbol(instruction.text):
            issues.append(
                AuditIssue(
                    category="instruction_trademark_symbol",
                    recipe_id=recipe.external_id,
                    detail=f"Instruction {instruction.step_number} contains trademark symbol",
                )
            )
            break

    return issues


def _ingredient_quality_issues(recipe: StoredRecipe) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for ingredient in recipe.ingredients:
        if _has_compact_quantity_leak(ingredient):
            issues.append(
                AuditIssue(
                    category="ingredient_compact_quantity_leak",
                    recipe_id=recipe.external_id,
                    detail=f"Ingredient has compact quantity leak: {ingredient.canonical_name}",
                )
            )
        if _contains_trademark_symbol(ingredient.canonical_name) or _contains_trademark_symbol(
            ingredient.preparation or ""
        ):
            issues.append(
                AuditIssue(
                    category="ingredient_trademark_symbol",
                    recipe_id=recipe.external_id,
                    detail=f"Ingredient contains trademark symbol: {ingredient.canonical_name}",
                )
            )
        if _looks_unparsed(ingredient):
            issues.append(
                AuditIssue(
                    category="ingredient_unparsed",
                    recipe_id=recipe.external_id,
                    detail=f"Unparsed ingredient: {ingredient.canonical_name}",
                )
            )
            break

    return issues


def _read_jobs(path: Path) -> list[CorpusJob]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as jobs_file:
        reader = csv.DictReader(jobs_file)
        return [
            CorpusJob(
                provider=(row.get("provider") or "").strip(),
                name=(row.get("name") or "").strip(),
                url=((row.get("url") or "").strip() or None),
            )
            for row in reader
            if (row.get("provider") or "").strip() and (row.get("name") or "").strip()
        ]


def _read_manifest(path: Path) -> list[RecipeNameImportResult]:
    if not path.exists():
        return []
    entries: list[RecipeNameImportResult] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entries.append(RecipeNameImportResult.model_validate_json(line))
        except ValueError:
            continue
    return entries


def _active_recipe_ids(
    jobs: list[CorpusJob],
    manifest_entries: list[RecipeNameImportResult],
    cached_recipe_ids: set[str],
    issues: list[AuditIssue],
) -> set[str]:
    active_recipe_ids: set[str] = set()
    imported_entries = [
        entry
        for entry in manifest_entries
        if entry.status == "imported" and entry.recipe_id is not None and entry.recipe_id in cached_recipe_ids
    ]

    for job in jobs:
        matching_entry = next((entry for entry in imported_entries if _manifest_entry_matches_job(entry, job)), None)
        if matching_entry is None or matching_entry.recipe_id is None:
            issues.append(
                AuditIssue(
                    category="active_job_missing_cache",
                    recipe_id=None,
                    detail=f"{job.provider}/{job.name} has no cached imported recipe",
                )
            )
            continue
        active_recipe_ids.add(matching_entry.recipe_id)

    return active_recipe_ids


def _manifest_entry_matches_job(entry: RecipeNameImportResult, job: CorpusJob) -> bool:
    if entry.provider != job.provider:
        return False
    if job.url:
        return entry.source_url == job.url
    return entry.name == job.name


def _contains_presentation_markup(text: str) -> bool:
    return bool(re.search(r"<[^>]+>", text) or "**" in text)


def _contains_trademark_symbol(text: str) -> bool:
    return bool(_TRADEMARK_SYMBOL_PATTERN.search(text))


def _has_compact_quantity_leak(ingredient: StoredIngredient) -> bool:
    if ingredient.quantity == 0 and not ingredient.unit:
        return False
    return bool(_COMPACT_QUANTITY_LEAK_PATTERN.search(ingredient.canonical_name))


def _is_all_zero_nutrition(nutrition: StoredNutrition | None) -> bool:
    if nutrition is None:
        return False
    return all(
        value == 0
        for value in (
            nutrition.calories,
            nutrition.protein_g,
            nutrition.carbohydrates_g,
            nutrition.fat_g,
            nutrition.fibre_g,
            nutrition.sugar_g,
            nutrition.sodium_mg,
        )
    )


def _looks_unparsed(ingredient: StoredIngredient) -> bool:
    if ingredient.quantity != 0 or ingredient.unit:
        return False
    return bool(
        re.search(r"^\s*\d", ingredient.canonical_name)
        or re.search(r"\b(?:g|kg|grams?|ml|litres?|tsp|tbsp|unit\(s\))\b", ingredient.canonical_name)
    )


if __name__ == "__main__":
    raise SystemExit(main())
