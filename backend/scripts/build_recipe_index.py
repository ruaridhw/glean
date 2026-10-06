#!/usr/bin/env python3
"""Rebuild the recipe corpus search index from every recipe blob.

Run once after bulk-loading recipes into a corpus (for example, after copying a
local corpus to S3); `RecipeCorpusStore.save` keeps the index current after that.

    uv run python scripts/build_recipe_index.py --bucket glean-recipe-cache-prod-040396448697
    uv run python scripts/build_recipe_index.py --cache-dir .cache/glean_recipe_cache
"""

from __future__ import annotations

import argparse
from pathlib import Path

from glean.recipe_api.blob_store import BlobStore, FilesystemBlobStore, S3BlobStore
from glean.recipes.corpus import RecipeCorpusStore


def main() -> int:
    args = _parse_args()
    store: BlobStore
    if args.bucket:
        store = S3BlobStore(args.bucket, region=args.region, prefix="corpus/")
    else:
        store = FilesystemBlobStore(args.cache_dir / "corpus")
    count = RecipeCorpusStore(store).rebuild_index()
    print(f"Indexed {count} recipes")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the recipe corpus search index.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bucket", help="S3 recipe-cache bucket holding the corpus/ prefix.")
    source.add_argument("--cache-dir", type=Path, help="Local recipe cache root holding corpus/.")
    parser.add_argument("--region", default="eu-west-2")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
