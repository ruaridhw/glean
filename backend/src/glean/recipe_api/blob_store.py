"""Storage seam for the recipe cache + corpus.

Both the ephemeral recipe-api HTTP cache and the durable recipe corpus are just
key→JSON-text blobs. This module hides *where* those blobs live behind one small
interface with two adapters:

- `FilesystemBlobStore` — the `.cache/...` tree used for local dev and tests.
- `S3BlobStore` — an S3 bucket, used when `s3_recipe_cache_bucket` is configured
  (i.e. deployed environments), because a Lambda's only writable path is `/tmp`
  and that is per-execution-environment ephemeral.

Selection is by environment: if a cache bucket is configured we use S3, otherwise
the filesystem. Keys are `/`-separated, `.json`-suffixed relative paths so the two
adapters lay data out identically.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from glean.observability import logger

DEFAULT_CACHE_DIR = Path(".cache/glean_recipe_cache")


class BlobStore(Protocol):
    """A minimal key→text blob store. Missing/unreadable keys read as ``None``."""

    def read(self, key: str) -> str | None: ...
    def write(self, key: str, content: str) -> None: ...
    def list_keys(self, prefix: str = "") -> list[str]: ...


class FilesystemBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, key: str) -> str | None:
        try:
            return (self.root / key).read_text()
        except OSError:
            return None

    def write(self, key: str, content: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with NamedTemporaryFile(
                "w", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as handle:
                handle.write(content)
                temp_path = Path(handle.name)
            temp_path.replace(path)
        except OSError:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def list_keys(self, prefix: str = "") -> list[str]:
        if not self.root.exists():
            return []
        found = (path.relative_to(self.root).as_posix() for path in self.root.rglob("*.json") if path.is_file())
        return sorted(key for key in found if key.startswith(prefix))


class S3BlobStore:
    def __init__(self, bucket: str, *, region: str, prefix: str = "") -> None:
        import boto3  # noqa: PLC0415 - match the inline-boto3 pattern used elsewhere in the codebase

        self._bucket = bucket
        self._prefix = prefix
        self._client = boto3.client("s3", region_name=region)

    def read(self, key: str) -> str | None:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._prefix + key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"NoSuchKey", "404", "NoSuchBucket"}:
                logger.warning("recipe blob read failed", extra={"key": key, "code": code})
            return None
        return response["Body"].read().decode("utf-8")

    def write(self, key: str, content: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=self._prefix + key, Body=content.encode("utf-8"))

    def list_keys(self, prefix: str = "") -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        found: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix + prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"][len(self._prefix) :]
                if key.endswith(".json"):
                    found.append(key)
        return sorted(found)


def _make_store(subpath: str) -> BlobStore:
    from glean.config import get_settings  # noqa: PLC0415 - avoid a circular import at module load

    settings = get_settings()
    if settings.s3_recipe_cache_bucket:
        prefix = f"{subpath}/" if subpath else ""
        return S3BlobStore(settings.s3_recipe_cache_bucket, region=settings.aws_region, prefix=prefix)
    root = DEFAULT_CACHE_DIR / subpath if subpath else DEFAULT_CACHE_DIR
    return FilesystemBlobStore(root)


@lru_cache(maxsize=1)
def get_recipe_cache_store() -> BlobStore:
    """Blob store for the ephemeral recipe-api HTTP response cache."""
    return _make_store("")


@lru_cache(maxsize=1)
def get_recipe_corpus_store() -> BlobStore:
    """Blob store for the durable recipe corpus."""
    return _make_store("corpus")
