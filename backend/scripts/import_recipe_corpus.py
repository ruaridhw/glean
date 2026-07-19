#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from glean.config import get_settings
from glean.llm import LLMRouter
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.offline import OfflineRecipeImportJob, OfflineRecipeImportResult, import_offline_recipes


class CorpusImportJob(OfflineRecipeImportJob):
    name: str
    url: str


def main() -> int:
    args = _parse_args()
    jobs = read_jobs_file(args.jobs_file)

    llm_router = _NoLlmRouter() if args.fail_on_llm else _create_llm_router()
    results = run_jobs(
        jobs,
        llm_router=llm_router,
        corpus=RecipeCorpusStore(root=args.cache_dir),
        manifest_path=args.manifest,
        rate_limit_seconds=args.rate_limit_seconds,
    )

    imported_count = sum(result.status == "imported" for result in results)
    skipped_count = sum(result.status == "skipped" for result in results)
    failed_count = sum(result.status == "failed" for result in results)

    print(f"Recipe corpus import complete: {imported_count} imported, {skipped_count} skipped, {failed_count} failed")
    return 1 if failed_count else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import recipe URLs into the local cache.")
    parser.add_argument("--jobs-file", required=True, type=Path, help="CSV with name,url columns.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--fail-on-llm", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0)
    return parser.parse_args()


def read_jobs_file(path: Path) -> list[CorpusImportJob]:
    with path.open(newline="", encoding="utf-8") as jobs_file:
        reader = csv.DictReader(jobs_file)
        if reader.fieldnames is None:
            raise ValueError("jobs CSV must include name and url columns")
        fieldnames = set(reader.fieldnames)
        if "provider" in fieldnames:
            raise ValueError("jobs CSV must not include provider")
        if not {"name", "url"}.issubset(fieldnames):
            raise ValueError("jobs CSV must include name and url columns")
        return [
            CorpusImportJob(
                name=(row.get("name") or "").strip(),
                url=(row.get("url") or "").strip(),
            )
            for row in reader
            if (row.get("name") or "").strip() and (row.get("url") or "").strip()
        ]


def run_jobs(
    jobs: list[CorpusImportJob],
    *,
    llm_router: Any,
    corpus: RecipeCorpusStore,
    manifest_path: Path,
    rate_limit_seconds: float,
) -> list[OfflineRecipeImportResult]:
    return import_offline_recipes(
        jobs=jobs,
        llm_router=llm_router,
        corpus=corpus,
        manifest_path=manifest_path,
        rate_limit_seconds=rate_limit_seconds,
    )


def _create_llm_router() -> LLMRouter:
    return LLMRouter.from_settings(get_settings())


class _NoLlmRouter:
    def invoke(self, *_: Any, **__: Any) -> None:
        raise RuntimeError("LLM invocation is disabled by --fail-on-llm")


if __name__ == "__main__":
    raise SystemExit(main())
