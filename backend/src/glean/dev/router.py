import json
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, UploadFile

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.observability import logger

router = APIRouter(prefix="/dev", tags=["dev"])

# The receipts bucket's lifecycle keeps this prefix for ~30 days (see template.yaml).
EXPORT_PREFIX = "db-exports"


# Backup downloads are fetched straight after listing, so the links need not outlive a few minutes.
DOWNLOAD_URL_TTL_SECONDS = 300
# An agent that transformed a backup uploads it beside a copy of this object, as `<id>PREPARED`, whose optional
# JSON body `{"note": "..."}` labels it in the app.
PREPARED_MARKER = "PREPARED"
_SQLITE_HEADER_BYTES = 100
_SQLITE_MAGIC = b"SQLite format 3\x00"
_USER_VERSION_OFFSET = 60


def _schema_version(header: bytes) -> int | None:
    """The drift schema version, which drift keeps in SQLite's ``user_version`` header field."""
    if len(header) < _SQLITE_HEADER_BYTES or not header.startswith(_SQLITE_MAGIC):
        return None
    return int.from_bytes(header[_USER_VERSION_OFFSET : _USER_VERSION_OFFSET + 4], "big")


def _read_header(s3: Any, bucket: str, key: str, size: int) -> bytes:
    """The first bytes of a backup, or nothing for an object that is empty or cannot be read.

    One bad object must not fail the whole listing: it is listed with an unknown schema version, and the app
    refuses it at restore time.
    """
    if size == 0:
        return b""
    try:
        return s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{_SQLITE_HEADER_BYTES - 1}")["Body"].read()
    except ClientError:
        return b""


def _prepared_note(s3: Any, bucket: str, key: str) -> str | None:
    """The agent's free-text note from a PREPARED marker; a marker that is empty or not JSON just has no note."""
    try:
        note = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read()).get("note")
    except (ValueError, AttributeError, ClientError):
        return None
    return note if isinstance(note, str) and note else None


@router.get("/backups")
async def list_backups(
    user_id: str = Depends(verify_cognito_token),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict:
    """List the signed-in user's own backups, newest first, each with a short-lived download URL.

    The listing is scoped by the token's Cognito subject alone; the request carries no input that could
    widen it to another user's prefix.
    """
    s3 = boto3.client("s3", region_name=settings.aws_region)
    bucket = settings.s3_receipts_bucket
    user_prefix = f"{EXPORT_PREFIX}/{user_id}/"
    # One call returns at most 1000 keys, in key order; without paging, later (newer, prepared) backups vanish.
    listing = [
        item
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=user_prefix)
        for item in page.get("Contents", [])
    ]
    keys = {item["Key"] for item in listing}
    backups = []
    for item in listing:
        key = item["Key"]
        if not key.endswith("/glean.db"):
            continue
        header = _read_header(s3, bucket, key, item["Size"])
        backup_id = key.removesuffix("glean.db")
        prepared = f"{backup_id}{PREPARED_MARKER}" in keys
        backups.append(
            {
                "id": backup_id,
                "created_at": item["LastModified"].isoformat(),
                "prepared": prepared,
                "label": _prepared_note(s3, bucket, f"{backup_id}{PREPARED_MARKER}") if prepared else None,
                "schema_version": _schema_version(header),
                "size": item["Size"],
                "download_url": s3.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=DOWNLOAD_URL_TTL_SECONDS
                ),
            }
        )
    backups.sort(key=lambda b: b["id"], reverse=True)
    backups.sort(key=lambda b: not b["prepared"])  # stable: prepared first, each group newest first
    return {"backups": backups}


@router.post("/export-db")
async def export_db(
    database: UploadFile = File(...),  # noqa: B008
    log: UploadFile = File(...),  # noqa: B008
    user_id: str = Depends(verify_cognito_token),
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict:
    """Store the signed-in user's own database snapshot and app log under a fresh, timestamped prefix.

    Object names are fixed, so an upload's filename can never steer the key, and the microsecond timestamp
    keeps back-to-back exports apart.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"{EXPORT_PREFIX}/{user_id}/{stamp}/"
    keys = {"database": f"{prefix}glean.db", "log": f"{prefix}app.log"}
    contents = {"database": await database.read(), "log": await log.read()}

    s3 = boto3.client("s3", region_name=settings.aws_region)
    for part, key in keys.items():
        s3.put_object(Bucket=settings.s3_receipts_bucket, Key=key, Body=contents[part])
    logger.info("diagnostics exported", extra={"prefix": prefix, "bytes": {k: len(v) for k, v in contents.items()}})
    return {"status": "uploaded", "prefix": prefix, "keys": keys}
