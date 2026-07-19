# backend/src/glean/receipts/service.py
from __future__ import annotations

import base64
import json
import uuid
from typing import TYPE_CHECKING

import boto3
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.content import create_image_block, create_text_block

from glean.llm import Feature
from glean.observability import logger, tracer
from glean.receipts.schemas import DescribeRequest, ScanResponse

if TYPE_CHECKING:
    from glean.llm import LLMRouter

NORMALISE_SYSTEM_PROMPT = """You are a grocery ingredient normaliser.
Given a list of receipt line items (name, quantity, price), return structured items with:
- name: canonical lowercase ingredient name (e.g. "chicken breast", "whole milk")
- quantity: numeric quantity in a sensible base unit (grams for solids, ml for liquids, units for countables)
- unit: "g", "ml", or "units"
- unit_price: price per normalised unit (e.g. if 500g costs £3.50, unit_price = 3.50/500 = 0.007)
- confidence: 0.0-1.0 reflecting how certain you are about the normalisation"""

VISION_SYSTEM_PROMPT = """You are a grocery receipt scanner and ingredient normaliser.
Given an image of a grocery receipt, extract all line items and return structured items with:
- name: canonical lowercase ingredient name (e.g. "chicken breast", "whole milk")
- quantity: numeric quantity in a sensible base unit (grams for solids, ml for liquids, units for countables)
- unit: "g", "ml", or "units"
- unit_price: price per normalised unit (e.g. if 500g costs £3.50, unit_price = 3.50/500 = 0.007)
- confidence: 0.0-1.0 reflecting how certain you are about the extraction and normalisation"""


def _extract_textract_lines(textract_response: dict) -> list[dict]:
    lines = []
    for doc in textract_response.get("ExpenseDocuments", []):
        for group in doc.get("LineItemGroups", []):
            for line in group.get("LineItems", []):
                item: dict = {}
                for field in line.get("LineItemExpenseFields", []):
                    field_type = field["Type"]["Text"]
                    value = field["ValueDetection"]["Text"]
                    confidence = field["ValueDetection"]["Confidence"]
                    if field_type == "ITEM":
                        item["name"] = value
                        item["confidence"] = confidence / 100
                    elif field_type == "QUANTITY":
                        item["quantity_raw"] = value
                    elif field_type == "PRICE":
                        item["price"] = value
                if "name" in item:
                    lines.append(item)
    return lines


@tracer.capture_method
def _scan_via_textract(image_bytes: bytes, *, llm_router: LLMRouter, aws_region: str, s3_bucket: str) -> ScanResponse:
    """OCR via AWS Textract, then normalise extracted text with the LLM."""
    s3 = boto3.client("s3", region_name=aws_region)
    s3_key = f"receipts/tmp/{uuid.uuid4()}.jpg"
    logger.info("uploading receipt to s3", extra={"key": s3_key, "bytes": len(image_bytes)})
    s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=image_bytes)

    textract = boto3.client("textract", region_name=aws_region)
    try:
        textract_response = textract.analyze_expense(Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}})
        lines = _extract_textract_lines(textract_response)
        logger.info("textract extracted lines", extra={"count": len(lines)})
    finally:
        s3.delete_object(Bucket=s3_bucket, Key=s3_key)

    response = llm_router.invoke(
        Feature.RECEIPT_SCAN,
        ScanResponse,
        [SystemMessage(content=NORMALISE_SYSTEM_PROMPT), HumanMessage(content=json.dumps(lines))],
    )
    logger.info("llm normalised items")
    return response


@tracer.capture_method
def _scan_via_vision(image_bytes: bytes, *, llm_router: LLMRouter) -> ScanResponse:
    """Send the receipt image directly to a vision-capable LLM for OCR + normalisation."""
    b64 = base64.b64encode(image_bytes).decode()
    image_block = create_image_block(base64=b64, mime_type="image/jpeg")
    response = llm_router.invoke(
        Feature.RECEIPT_SCAN,
        ScanResponse,
        [
            SystemMessage(content=VISION_SYSTEM_PROMPT),
            HumanMessage(
                content_blocks=[
                    create_text_block("Extract and normalise all items from this receipt."),
                    image_block,
                ]
            ),
        ],
    )
    logger.info("vision model scanned receipt")
    return response


@tracer.capture_method
def scan_receipt(
    image_bytes: bytes,
    *,
    ocr_mode: str,
    llm_router: LLMRouter,
    aws_region: str,
    s3_bucket: str,
) -> ScanResponse:
    if ocr_mode == "vision":
        return _scan_via_vision(image_bytes, llm_router=llm_router)
    return _scan_via_textract(image_bytes, llm_router=llm_router, aws_region=aws_region, s3_bucket=s3_bucket)


@tracer.capture_method
def describe_purchase(request: DescribeRequest, *, llm_router: LLMRouter) -> ScanResponse:
    return llm_router.invoke(
        Feature.PANTRY_PURCHASE_DESCRIPTION,
        ScanResponse,
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {request.text}"),
        ],
    )
