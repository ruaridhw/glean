from datetime import UTC, datetime

import boto3
from fastapi import APIRouter, Depends, File, UploadFile

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.observability import logger

router = APIRouter(prefix="/dev", tags=["dev"])

# The receipts bucket's lifecycle keeps this prefix for ~30 days (see template.yaml).
EXPORT_PREFIX = "db-exports"


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
