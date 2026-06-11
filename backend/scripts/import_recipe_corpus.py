#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glean.config import get_settings
from glean.llm import create_chat_model
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.offline import RecipeNameImportJob, RecipeNameImportResult, import_recipe_names
from glean.recipes.providers import ProviderRegistry, import_url_to_canonical
from glean.recipes.stored import RecipeImportError


@dataclass(frozen=True)
class CorpusImportJob:
    provider: str
    name: str
    url: str | None = None


def main() -> int:
    args = _parse_args()
    if args.jobs_file:
        jobs = read_jobs_file(args.jobs_file)
    else:
        jobs = _read_provider_name_jobs(args.provider, args.names_file)

    model = _NoLlm() if args.fail_on_llm else _create_configured_model()
    results = run_jobs(
        jobs,
        model=model,
        corpus=RecipeCorpusStore(root=args.cache_dir),
        registry=ProviderRegistry.default(),
        manifest_path=args.manifest,
        rate_limit_seconds=args.rate_limit_seconds,
    )

    imported_count = sum(result.status == "imported" for result in results)
    skipped_count = sum(result.status == "skipped" for result in results)
    failed_count = sum(result.status == "failed" for result in results)

    print(
        "Recipe corpus import complete: " f"{imported_count} imported, {skipped_count} skipped, {failed_count} failed"
    )
    return 1 if failed_count else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a provider recipe-name corpus into the local cache.")
    parser.add_argument("--jobs-file", type=Path, help="CSV with provider,name,url columns. url may be blank.")
    parser.add_argument("--provider")
    parser.add_argument("--names-file", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--fail-on-llm", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0)
    args = parser.parse_args()
    if args.jobs_file and (args.provider or args.names_file):
        parser.error("--jobs-file cannot be combined with --provider or --names-file")
    if not args.jobs_file and (not args.provider or not args.names_file):
        parser.error("either --jobs-file or both --provider and --names-file are required")
    return args


def read_jobs_file(path: Path) -> list[CorpusImportJob]:
    with path.open(newline="", encoding="utf-8") as jobs_file:
        reader = csv.DictReader(jobs_file)
        if reader.fieldnames is None or not {"provider", "name"}.issubset(reader.fieldnames):
            raise ValueError("jobs CSV must include provider and name columns")
        return [
            CorpusImportJob(
                provider=(row.get("provider") or "").strip(),
                name=(row.get("name") or "").strip(),
                url=((row.get("url") or "").strip() or None),
            )
            for row in reader
            if (row.get("provider") or "").strip() and (row.get("name") or "").strip()
        ]


def run_jobs(
    jobs: list[CorpusImportJob],
    *,
    model: Any,
    corpus: RecipeCorpusStore,
    registry: ProviderRegistry,
    manifest_path: Path,
    rate_limit_seconds: float,
) -> list[RecipeNameImportResult]:
    results: list[RecipeNameImportResult] = []
    has_processed_non_skipped_job = False
    imported_url_jobs = _load_imported_url_manifest_entries(manifest_path, corpus=corpus)

    for job in jobs:
        if has_processed_non_skipped_job and rate_limit_seconds > 0:
            time.sleep(rate_limit_seconds)
        if job.url:
            result = _import_url_job(
                job,
                model=model,
                corpus=corpus,
                registry=registry,
                manifest_path=manifest_path,
                imported_url_jobs=imported_url_jobs,
            )
        else:
            result = import_recipe_names(
                [RecipeNameImportJob(provider=job.provider, name=job.name)],
                model=model,
                corpus=corpus,
                registry=registry,
                manifest_path=manifest_path,
                rate_limit_seconds=0.0,
            )[0]
        results.append(result)
        if job.url and result.status == "imported" and result.recipe_id is not None and result.source_url is not None:
            imported_url_jobs[(job.provider, job.url)] = result
        if result.status != "skipped":
            has_processed_non_skipped_job = True
    return results


def _import_url_job(
    job: CorpusImportJob,
    *,
    model: Any,
    corpus: RecipeCorpusStore,
    registry: ProviderRegistry,
    manifest_path: Path,
    imported_url_jobs: dict[tuple[str, str], RecipeNameImportResult],
) -> RecipeNameImportResult:
    url = job.url
    if url is None:
        raise ValueError("URL import jobs must include a URL")
    if existing_result := imported_url_jobs.get((job.provider, url)):
        return RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="skipped",
            source_url=existing_result.source_url,
            recipe_id=existing_result.recipe_id,
        )
    if existing_recipe := corpus.get_by_source_url(url):
        return RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="skipped",
            source_url=url,
            recipe_id=existing_recipe.external_id,
        )

    try:
        parse_result = import_url_to_canonical(url, model=model, registry=registry)
        if parse_result.recipe is None:
            result = RecipeNameImportResult(
                provider=job.provider,
                name=job.name,
                status="failed",
                source_url=url,
                error_category=parse_result.failure_category or "import_failed",
                error_message="Recipe import did not return a recipe",
            )
        else:
            recipe = corpus.save(parse_result.recipe)
            result = RecipeNameImportResult(
                provider=job.provider,
                name=job.name,
                status="imported",
                source_url=url,
                recipe_id=recipe.external_id,
            )
    except RecipeImportError as exc:
        result = RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="failed",
            source_url=url,
            error_category=exc.category,
            error_message=exc.message,
        )
    except Exception as exc:
        result = RecipeNameImportResult(
            provider=job.provider,
            name=job.name,
            status="failed",
            source_url=url,
            error_category="unexpected_error",
            error_message=str(exc),
        )

    _append_manifest_entry(manifest_path, result)
    return result


def _load_imported_url_manifest_entries(
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
        if (
            result.status == "imported"
            and result.recipe_id
            and result.source_url
            and corpus.get(result.recipe_id) is not None
        ):
            imported[(result.provider, result.source_url)] = result
    return imported


def _read_recipe_names(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _read_provider_name_jobs(provider: str, names_file: Path) -> list[CorpusImportJob]:
    return [CorpusImportJob(provider=provider, name=name) for name in _read_recipe_names(names_file)]


def _append_manifest_entry(manifest_path: Path, result: RecipeNameImportResult) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        manifest_file.write(json.dumps(result.model_dump(mode="json"), sort_keys=True) + "\n")
        manifest_file.flush()


def _create_configured_model() -> Any:
    settings = get_settings()
    return create_chat_model(settings.llm_model, api_key=settings.openrouter_api_key)


class _NoLlm:
    def invoke(self, *_: Any, **__: Any) -> None:
        raise RuntimeError("LLM invocation is disabled by --fail-on-llm")


if __name__ == "__main__":
    raise SystemExit(main())
