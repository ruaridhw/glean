from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from pydantic import BaseModel

from glean.recipes.providers import (
    ProviderRegistry,
    discover_first_recipe_url,
    fetch_public_https,
    import_url_to_canonical,
)
from glean.recipes.stored import RecipeImportError

__all__ = ["RecipeNameImportJob", "RecipeNameImportResult", "import_recipe_names"]

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from langchain_core.language_models import BaseChatModel

    from glean.recipes.corpus import RecipeCorpusStore


class RecipeNameImportJob(BaseModel):
    provider: str
    name: str


class RecipeNameImportResult(BaseModel):
    provider: str
    name: str
    status: str
    source_url: str | None = None
    recipe_id: str | None = None
    error_category: str | None = None
    error_message: str | None = None


if TYPE_CHECKING:
    _vulture_pydantic_field_references = (
        RecipeNameImportResult.error_category,
        RecipeNameImportResult.error_message,
    )


def import_recipe_names(
    jobs: Iterable[RecipeNameImportJob],
    *,
    model: BaseChatModel,
    corpus: RecipeCorpusStore,
    registry: ProviderRegistry,
    manifest_path: Path,
    rate_limit_seconds: float = 0.0,
) -> list[RecipeNameImportResult]:
    existing_imports = _load_imported_manifest_entries(manifest_path, corpus=corpus)
    results: list[RecipeNameImportResult] = []
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    has_processed_non_skipped_job = False

    for job in jobs:
        existing_result = existing_imports.get((job.provider, job.name))
        if existing_result is not None:
            results.append(
                RecipeNameImportResult(
                    provider=job.provider,
                    name=job.name,
                    status="skipped",
                    source_url=existing_result.source_url,
                    recipe_id=existing_result.recipe_id,
                )
            )
            continue

        if has_processed_non_skipped_job and rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)

        result = _import_recipe_name(job, model=model, corpus=corpus, registry=registry)
        _append_manifest_entry(manifest_path, result)
        results.append(result)
        has_processed_non_skipped_job = True
        if result.status == "imported" and result.recipe_id is not None:
            existing_imports[(result.provider, result.name)] = result

    return results


def _load_imported_manifest_entries(
    manifest_path: Path,
    *,
    corpus: RecipeCorpusStore,
) -> dict[tuple[str, str], RecipeNameImportResult]:
    if not manifest_path.exists():
        return {}

    imported: dict[tuple[str, str], RecipeNameImportResult] = {}
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            result = RecipeNameImportResult.model_validate_json(line)
        except ValueError:
            continue
        if result.status == "imported" and result.recipe_id and corpus.get(result.recipe_id) is not None:
            imported[(result.provider, result.name)] = result
    return imported


def _import_recipe_name(
    job: RecipeNameImportJob,
    *,
    model: BaseChatModel,
    corpus: RecipeCorpusStore,
    registry: ProviderRegistry,
) -> RecipeNameImportResult:
    try:
        provider = registry.provider_by_name(job.provider)
        search_url = provider.search_url(job.name)
        if urlparse(search_url).scheme.lower() != "https":
            return RecipeNameImportResult(
                provider=job.provider,
                name=job.name,
                status="failed",
                error_category="unsupported_provider_search",
                error_message=f"Provider search URL must use HTTPS: {search_url}",
            )

        search_page = fetch_public_https(search_url)
        source_url = discover_first_recipe_url(search_page.text, base_url=search_url, provider=provider)
        if source_url is None:
            return RecipeNameImportResult(
                provider=job.provider,
                name=job.name,
                status="failed",
                error_category="search_no_result",
                error_message="No recipe result found in provider search",
            )

        parse_result = import_url_to_canonical(source_url, model=model, registry=registry)
        if parse_result.recipe is None:
            return RecipeNameImportResult(
                provider=job.provider,
                name=job.name,
                status="failed",
                source_url=source_url,
                error_category=parse_result.failure_category or "import_failed",
                error_message="Recipe import did not return a recipe",
            )

        recipe = corpus.save(parse_result.recipe)
        return RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="imported",
            source_url=source_url,
            recipe_id=recipe.external_id,
        )
    except RecipeImportError as exc:
        return RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="failed",
            error_category=exc.category,
            error_message=exc.message,
        )
    except Exception as exc:
        return RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="failed",
            error_category="unexpected_error",
            error_message=str(exc),
        )


def _append_manifest_entry(manifest_path: Path, result: RecipeNameImportResult) -> None:
    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        manifest_file.write(json.dumps(result.model_dump(mode="json"), sort_keys=True) + "\n")
        manifest_file.flush()
