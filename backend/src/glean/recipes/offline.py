from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel

from glean.recipes.providers import import_url_to_canonical
from glean.recipes.stored import RecipeImportError

__all__ = ["OfflineRecipeImportJob", "OfflineRecipeImportResult", "import_offline_recipes"]

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from glean.llm import LLMRouter
    from glean.recipes.corpus import RecipeCorpusStore


class OfflineRecipeImportJob(BaseModel):
    name: str
    url: str


class OfflineRecipeImportResult(BaseModel):
    name: str
    status: str
    source_url: str | None = None
    recipe_id: str | None = None
    error_category: str | None = None
    error_message: str | None = None


if TYPE_CHECKING:
    _vulture_pydantic_field_references = (
        OfflineRecipeImportResult.error_category,
        OfflineRecipeImportResult.error_message,
    )


def import_offline_recipes(
    jobs: Iterable[OfflineRecipeImportJob],
    *,
    llm_router: LLMRouter,
    corpus: RecipeCorpusStore,
    manifest_path: Path,
    rate_limit_seconds: float = 0.0,
) -> list[OfflineRecipeImportResult]:
    existing_imports = _load_imported_manifest_entries(manifest_path, corpus=corpus)
    results: list[OfflineRecipeImportResult] = []
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    has_processed_non_skipped_job = False

    for job in jobs:
        existing_result = existing_imports.get(job.url)
        if existing_result is not None:
            results.append(
                OfflineRecipeImportResult(
                    name=job.name,
                    status="skipped",
                    source_url=existing_result.source_url,
                    recipe_id=existing_result.recipe_id,
                )
            )
            continue

        if has_processed_non_skipped_job and rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)

        result = _import_recipe_url(job, llm_router=llm_router, corpus=corpus)
        _append_manifest_entry(manifest_path, result)
        results.append(result)
        has_processed_non_skipped_job = True
        if result.status == "imported" and result.recipe_id is not None and result.source_url is not None:
            existing_imports[result.source_url] = result

    return results


def _load_imported_manifest_entries(
    manifest_path: Path,
    *,
    corpus: RecipeCorpusStore,
) -> dict[str, OfflineRecipeImportResult]:
    if not manifest_path.exists():
        return {}

    imported: dict[str, OfflineRecipeImportResult] = {}
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            result = OfflineRecipeImportResult.model_validate_json(line)
        except ValueError:
            continue
        if (
            result.status == "imported"
            and result.source_url
            and result.recipe_id
            and corpus.get(result.recipe_id) is not None
        ):
            imported[result.source_url] = result
    return imported


def _import_recipe_url(
    job: OfflineRecipeImportJob,
    *,
    llm_router: LLMRouter,
    corpus: RecipeCorpusStore,
) -> OfflineRecipeImportResult:
    if existing_recipe := corpus.get_by_source_url(job.url):
        return OfflineRecipeImportResult(
            name=job.name,
            status="skipped",
            source_url=job.url,
            recipe_id=existing_recipe.external_id,
        )

    try:
        parse_result = import_url_to_canonical(job.url, llm_router=llm_router)
        if parse_result.recipe is None:
            return OfflineRecipeImportResult(
                name=job.name,
                status="failed",
                source_url=job.url,
                error_category=parse_result.failure_category or "import_failed",
                error_message="Recipe import did not return a recipe",
            )

        recipe = corpus.save(parse_result.recipe)
        return OfflineRecipeImportResult(
            name=job.name,
            status="imported",
            source_url=job.url,
            recipe_id=recipe.external_id,
        )
    except RecipeImportError as exc:
        return OfflineRecipeImportResult(
            name=job.name,
            status="failed",
            source_url=job.url,
            error_category=exc.category,
            error_message=exc.message,
        )
    except Exception as exc:
        return OfflineRecipeImportResult(
            name=job.name,
            status="failed",
            source_url=job.url,
            error_category="unexpected_error",
            error_message=str(exc),
        )


def _append_manifest_entry(manifest_path: Path, result: OfflineRecipeImportResult) -> None:
    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        manifest_file.write(json.dumps(result.model_dump(mode="json"), sort_keys=True) + "\n")
        manifest_file.flush()
