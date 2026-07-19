# backend/src/glean/receipts/router.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Annotated/Depends at runtime.
from glean.receipts import service
from glean.receipts.schemas import DescribeRequest, ScanResponse

router = APIRouter(prefix="/receipts", tags=["receipts"], dependencies=[Depends(verify_cognito_token)])


@router.post("/scan", response_model=ScanResponse)
async def scan_receipt(
    file: Annotated[UploadFile, File()],
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ScanResponse:
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only image/jpeg and image/png are accepted")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")
    return service.scan_receipt(
        image_bytes,
        ocr_mode=settings.receipt_ocr_mode,
        llm_router=llm_router,
        aws_region=settings.aws_region,
        s3_bucket=settings.s3_receipts_bucket,
    )


@router.post("/describe", response_model=ScanResponse)
def describe_purchase(
    request: DescribeRequest,
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> ScanResponse:
    return service.describe_purchase(request, llm_router=llm_router)
