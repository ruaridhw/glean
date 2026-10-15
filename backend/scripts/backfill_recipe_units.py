#!/usr/bin/env python3
"""One-off backfill (#120): re-parse corpus ingredients that leaked a unit word into their name.

Local filesystem corpus only: there is deliberately no bucket option, so this can't reach S3.
Dry run by default; pass --write to rewrite the blobs.

    uv run python scripts/backfill_recipe_units.py --cache-dir .cache/glean_recipe_cache
    uv run python scripts/backfill_recipe_units.py --cache-dir .cache/glean_recipe_cache --write
"""

from __future__ import annotations

import argparse
from pathlib import Path

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.unit_backfill import backfill_unit_words


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    corpus = RecipeCorpusStore(FilesystemBlobStore(args.cache_dir / "corpus"))
    result = backfill_unit_words(corpus, dry_run=not args.write)
    verb = "Rewrote" if args.write else "Would rewrite"
    print(
        f"{verb} {result.ingredients_changed} ingredients in {result.recipes_changed} recipes "
        f"({result.recipes_scanned} scanned)"
    )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-parse corpus ingredients with a leaked unit word.")
    parser.add_argument("--cache-dir", required=True, type=Path, help="Local recipe cache root holding corpus/.")
    parser.add_argument("--write", action="store_true", help="Rewrite blobs (default is a dry run).")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
