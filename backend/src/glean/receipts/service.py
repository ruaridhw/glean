# backend/src/glean/receipts/service.py
from __future__ import annotations

import json
import uuid

import boto3
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import settings
from glean.llm import Feature, create_chat_model
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


def _default_model() -> BaseChatModel:
    return create_chat_model(settings.llm_provider, settings.llm_model, api_key=settings.anthropic_api_key)


@tracer.capture_method
def scan_receipt(image_bytes: bytes, *, model: BaseChatModel | None = None) -> ScanResponse:
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

    model = model or _default_model()
    result = model.invoke(
        [SystemMessage(content=NORMALISE_SYSTEM_PROMPT), HumanMessage(content=json.dumps(lines))],
        config={"metadata": {"feature": Feature.RECEIPT_SCAN}},
    )
    logger.info("claude normalised items")

    items = [ParsedIngredient(**item) for item in json.loads(result.content)]
    return ScanResponse(items=items)


@tracer.capture_method
def describe_purchase(request: DescribeRequest, *, model: BaseChatModel | None = None) -> ScanResponse:
    model = model or _default_model()
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {request.text}"),
        ],
        config={"metadata": {"feature": Feature.RECEIPT_SCAN}},
    )
    items = [ParsedIngredient(**item) for item in json.loads(result.content)]
    return ScanResponse(items=items)
