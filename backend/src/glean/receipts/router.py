# backend/src/glean/receipts/router.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from glean.config import Settings, get_settings
from glean.dependencies import verify_cognito_token
from glean.llm import Feature, LLMRouter
from glean.receipts import service
from glean.receipts.schemas import DescribeRequest, ScanResponse

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/scan", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
async def scan_receipt(
    file: Annotated[UploadFile, File()],
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ScanResponse:
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only image/jpeg and image/png are accepted")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")
    llm_router = LLMRouter.from_settings(settings)
    model = llm_router.chat_model(Feature.RECEIPT_SCAN)
    return service.scan_receipt(
        image_bytes,
        ocr_mode=settings.receipt_ocr_mode,
        model=model,
        aws_region=settings.aws_region,
        s3_bucket=settings.s3_receipts_bucket,
        vision_model=model,
    )


@router.post("/describe", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
def describe_purchase(
    request: DescribeRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ScanResponse:
    model = LLMRouter.from_settings(settings).chat_model(Feature.PANTRY_PURCHASE_DESCRIPTION)
    return service.describe_purchase(request, model=model)
