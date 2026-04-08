# backend/src/glean/receipts/router.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from glean.dependencies import verify_cognito_token
from glean.receipts import service
from glean.receipts.schemas import DescribeRequest, ScanResponse

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/scan", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
async def scan_receipt(file: Annotated[UploadFile, File()]) -> ScanResponse:
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only image/jpeg and image/png are accepted")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")
    return service.scan_receipt(image_bytes)


@router.post("/describe", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
def describe_purchase(request: DescribeRequest) -> ScanResponse:
    return service.describe_purchase(request)
