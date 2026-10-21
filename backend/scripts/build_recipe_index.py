#!/usr/bin/env python3
"""Rebuild the recipe corpus search index — or, with `--table`, the S3 projection planning reads (F1/#162).

Run once after bulk-loading recipes into a corpus (for example, after copying a
local corpus to S3); `RecipeCorpusStore.save` keeps the index current after that.
In dynamo mode the same command rebuilds the projection from the table, which is the repair path when it
is missing or suspect.

    uv run python scripts/build_recipe_index.py --bucket glean-recipe-cache-prod-040396448697
    uv run python scripts/build_recipe_index.py --cache-dir .cache/glean_recipe_cache
    uv run python scripts/build_recipe_index.py --table glean-recipes-dev --bucket glean-recipe-cache-dev-040396448697
"""

from __future__ import annotations

import argparse
from pathlib import Path

from glean.recipes.corpus import open_corpus


def main() -> int:
    args = _parse_args()
    count = open_corpus(
        table=args.table, bucket=args.bucket, cache_dir=args.cache_dir, region=args.region
    ).rebuild_index()
    print(f"Indexed {count} recipes")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the recipe corpus search index.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bucket", help="S3 recipe-cache bucket: the corpus/ prefix, or the projection with --table.")
    source.add_argument(
        "--cache-dir", type=Path, help="Local recipe cache root: corpus/, or the projection with --table."
    )
    parser.add_argument("--table", help="DynamoDB recipes table: rebuild its S3 projection (F1/#162).")
    parser.add_argument("--region", default="eu-west-2")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
