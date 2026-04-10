# backend/src/glean/receipts/service.py
from __future__ import annotations

import base64
import json
import uuid
from typing import TYPE_CHECKING

import boto3
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.content import create_image_block

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.config import settings
from glean.llm import Feature, create_chat_model, get_default_model
from glean.observability import logger, tracer
from glean.receipts.schemas import DescribeRequest, ParsedIngredient, ScanResponse

NORMALISE_SYSTEM_PROMPT = """You are a grocery ingredient normaliser.
Given a list of receipt line items (name, quantity, price), return a JSON array of objects with:
- name: canonical lowercase ingredient name (e.g. "chicken breast", "whole milk")
- quantity: numeric quantity in a sensible base unit (grams for solids, ml for liquids, units for countables)
- unit: "g", "ml", or "units"
- unit_price: price per normalised unit (e.g. if 500g costs £3.50, unit_price = 3.50/500 = 0.007)
- confidence: 0.0-1.0 reflecting how certain you are about the normalisation

Respond with ONLY valid JSON. No markdown, no explanation."""

VISION_SYSTEM_PROMPT = """You are a grocery receipt scanner and ingredient normaliser.
Given an image of a grocery receipt, extract all line items and return a JSON array of objects with:
- name: canonical lowercase ingredient name (e.g. "chicken breast", "whole milk")
- quantity: numeric quantity in a sensible base unit (grams for solids, ml for liquids, units for countables)
- unit: "g", "ml", or "units"
- unit_price: price per normalised unit (e.g. if 500g costs £3.50, unit_price = 3.50/500 = 0.007)
- confidence: 0.0-1.0 reflecting how certain you are about the extraction and normalisation

Respond with ONLY valid JSON. No markdown, no explanation."""


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


def _normalise_items(raw_content: str) -> list[ParsedIngredient]:
    return [ParsedIngredient(**item) for item in json.loads(raw_content)]


@tracer.capture_method
def _scan_via_textract(image_bytes: bytes, *, model: BaseChatModel) -> ScanResponse:
    """OCR via AWS Textract, then normalise extracted text with the LLM."""
    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3_key = f"receipts/tmp/{uuid.uuid4()}.jpg"
    logger.info("uploading receipt to s3", extra={"key": s3_key, "bytes": len(image_bytes)})
    s3.put_object(Bucket=settings.s3_receipts_bucket, Key=s3_key, Body=image_bytes)

    textract = boto3.client("textract", region_name=settings.aws_region)
    try:
        textract_response = textract.analyze_expense(
            Document={"S3Object": {"Bucket": settings.s3_receipts_bucket, "Name": s3_key}}
        )
        lines = _extract_textract_lines(textract_response)
        logger.info("textract extracted lines", extra={"count": len(lines)})
    finally:
        s3.delete_object(Bucket=settings.s3_receipts_bucket, Key=s3_key)

    result = model.invoke(
        [SystemMessage(content=NORMALISE_SYSTEM_PROMPT), HumanMessage(content=json.dumps(lines))],
        config={"metadata": {"feature": Feature.RECEIPT_SCAN}},
    )
    logger.info("llm normalised items")
    return ScanResponse(items=_normalise_items(result.content))


@tracer.capture_method
def _scan_via_vision(image_bytes: bytes) -> ScanResponse:
    """Send the receipt image directly to a vision-capable LLM for OCR + normalisation."""
    vision_model = create_chat_model(
        settings.receipt_vision_model, api_key=settings.openrouter_api_key
    )
    b64 = base64.b64encode(image_bytes).decode()
    image_block = create_image_block(base64=b64, mime_type="image/jpeg")
    result = vision_model.invoke(
        [
            SystemMessage(content=VISION_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": "Extract and normalise all items from this receipt."},
                    image_block,
                ]
            ),
        ],
        config={"metadata": {"feature": Feature.RECEIPT_SCAN}},
    )
    logger.info("vision model scanned receipt")
    return ScanResponse(items=_normalise_items(result.content))


@tracer.capture_method
def scan_receipt(image_bytes: bytes, *, model: BaseChatModel | None = None) -> ScanResponse:
    if settings.receipt_ocr_mode == "vision":
        return _scan_via_vision(image_bytes)
    return _scan_via_textract(image_bytes, model=model or get_default_model())


@tracer.capture_method
def describe_purchase(request: DescribeRequest, *, model: BaseChatModel | None = None) -> ScanResponse:
    model = model or get_default_model()
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {request.text}"),
        ],
        config={"metadata": {"feature": Feature.RECEIPT_SCAN}},
    )
    return ScanResponse(items=_normalise_items(result.content))
