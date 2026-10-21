"""Open the corpus store a script should read or write (F1/#162: blobs, or DynamoDB plus its projection).

Every script takes the same two switches: `--table` picks the DynamoDB store, and `--bucket` /
`--cache-dir` says where the data lives — the `corpus/` prefix in blob mode, the projection document in
dynamo mode. Scripts without `--table` keep working exactly as before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glean.recipe_api.blob_store import DEFAULT_CACHE_DIR, FilesystemBlobStore, S3BlobStore
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.projection import FilesystemProjectionStore, S3ProjectionStore

if TYPE_CHECKING:
    from pathlib import Path

    from glean.recipes.projection import ProjectionStore

__all__ = ["open_corpus", "projection_store_for"]


def projection_store_for(
    *, bucket: str | None = None, cache_dir: Path | None = None, region: str = "eu-west-2"
) -> ProjectionStore:
    """Where the projection document lives: the recipe-cache bucket, or a local cache root."""
    if bucket:
        return S3ProjectionStore(bucket, region=region)
    return FilesystemProjectionStore(cache_dir or DEFAULT_CACHE_DIR)


def open_corpus(
    *,
    table: str | None = None,
    bucket: str | None = None,
    cache_dir: Path | None = None,
    region: str = "eu-west-2",
    corpus_dir: Path | None = None,
) -> RecipeCorpusStore:
    """The store `--table` selects, or the blob corpus at `corpus_dir` / `cache_dir/corpus` / `--bucket`."""
    if table:
        from glean.recipes.dynamo_corpus import DynamoCorpusBackend  # noqa: PLC0415 - boto3 only when used

        projection = projection_store_for(bucket=bucket, cache_dir=cache_dir, region=region)
        return RecipeCorpusStore(DynamoCorpusBackend(table, projection=projection, region=region))
    if bucket:
        return RecipeCorpusStore(BlobCorpusBackend(S3BlobStore(bucket, region=region, prefix="corpus/")))
    root = corpus_dir or ((cache_dir or DEFAULT_CACHE_DIR) / "corpus")
    return RecipeCorpusStore(BlobCorpusBackend(FilesystemBlobStore(root)))
