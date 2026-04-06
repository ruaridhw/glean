import boto3
from fastapi import APIRouter, Depends, File, UploadFile

from glean.config import settings
from glean.dependencies import verify_cognito_token
from glean.observability import logger

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/export-db", dependencies=[Depends(verify_cognito_token)])
async def export_db(file: UploadFile = File(...)) -> dict:  # noqa: B008
    contents = await file.read()
    s3 = boto3.client("s3", region_name=settings.aws_region)
    key = f"db-exports/{file.filename or 'glean.db'}"
    s3.put_object(Bucket=settings.s3_receipts_bucket, Key=key, Body=contents)
    logger.info("db exported", extra={"key": key, "bytes": len(contents)})
    return {"status": "uploaded", "key": key}
