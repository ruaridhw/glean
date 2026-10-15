from datetime import UTC, datetime

import boto3
from fastapi import APIRouter, Depends, File, UploadFile

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.observability import logger

router = APIRouter(prefix="/dev", tags=["dev"])

# The receipts bucket's lifecycle keeps this prefix for ~30 days (see template.yaml).
EXPORT_PREFIX = "db-exports"


# Backup downloads are fetched straight after listing, so the links need not outlive a few minutes.
DOWNLOAD_URL_TTL_SECONDS = 300
_SQLITE_HEADER_BYTES = 100
_SQLITE_MAGIC = b"SQLite format 3\x00"
_USER_VERSION_OFFSET = 60


def _schema_version(header: bytes) -> int | None:
    """The drift schema version, which drift keeps in SQLite's ``user_version`` header field."""
    if len(header) < _SQLITE_HEADER_BYTES or not header.startswith(_SQLITE_MAGIC):
        return None
    return int.from_bytes(header[_USER_VERSION_OFFSET : _USER_VERSION_OFFSET + 4], "big")


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
    listing = s3.list_objects_v2(Bucket=bucket, Prefix=user_prefix).get("Contents", [])
    backups = []
    for item in listing:
        key = item["Key"]
        if not key.endswith("/glean.db"):
            continue
        header = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{_SQLITE_HEADER_BYTES - 1}")["Body"].read()
        backups.append(
            {
                "id": key.removesuffix("glean.db"),
                "created_at": item["LastModified"].isoformat(),
                "prepared": False,
                "schema_version": _schema_version(header),
                "size": item["Size"],
                "download_url": s3.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=DOWNLOAD_URL_TTL_SECONDS
                ),
            }
        )
    backups.sort(key=lambda b: b["id"], reverse=True)
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
