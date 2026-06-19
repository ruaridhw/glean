from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import invoke_structured

RECEIPT_SCAN_RUBRIC = """You are evaluating a grocery receipt normalisation system.
Given a raw receipt line item name and the system's normalised output, rate the quality 1-5:

5 = Perfect canonical name, correct unit conversion, accurate price calculation
4 = Minor issue (slightly verbose name, small rounding difference)
3 = Acceptable but imprecise (name has extra words, unit roughly correct)
2 = Significant error (wrong unit type, major quantity error)
1 = Wrong (completely misidentified item)

Return structured data with a single score field from 1 to 5."""

SUGGESTIONS_RUBRIC = """You are evaluating a meal suggestion system.
Given a user's pantry state, dietary flags, and the system's suggestion, rate the quality 1-5:

5 = Excellent — uses expiring/urgent pantry items, reason is specific and references actual pantry data
4 = Good — reasonable suggestion, reason references pantry items by name
3 = Acceptable — valid recipe but reason is generic (e.g. "good for dinner")
2 = Poor — ignores pantry priorities or reason is vague/irrelevant
1 = Bad — violates dietary flags or completely irrelevant to pantry state

Return structured data with a single score field from 1 to 5."""

RECIPE_IMPORT_RUBRIC = """You are evaluating a recipe extraction system.
Given source HTML and the system's extracted recipe JSON, rate the extraction quality 1-5:

5 = Perfect — all fields accurately captured from the HTML
4 = Minor omission (missing optional field like cuisine or difficulty)
3 = Mostly correct but missing some ingredients or instruction steps
2 = Significant errors (wrong title, missing most ingredients)
1 = Completely wrong extraction

Return structured data with a single score field from 1 to 5."""

PURCHASE_DESCRIPTION_RUBRIC = """You are evaluating a grocery purchase description parser.
Given a user's free-text grocery purchase and the system's parsed pantry items, rate the quality 1-5:

5 = Excellent - all concrete purchased items are captured with sensible names, quantities, and units
4 = Good - captures the important items with only minor quantity or naming issues
3 = Acceptable - most items are present but at least one quantity or name is imprecise
2 = Poor - misses important items or uses unsuitable units
1 = Bad - mostly wrong or not useful for updating a pantry

Return structured data with a single score field from 1 to 5."""

SHOPPING_LIST_DESCRIPTION_RUBRIC = """You are evaluating a grocery shopping list parser.
Given a user's free-text shopping list and the system's structured shopping proposal, rate the quality 1-5:

5 = Excellent - all requested items are captured with practical shopping names, quantities, units, and categories
4 = Good - captures the important items with minor naming, category, or quantity issues
3 = Acceptable - most items are present but vague or incomplete
2 = Poor - misses important items or invents items not implied by the request
1 = Bad - mostly wrong or not useful for building a shopping list

Return structured data with a single score field from 1 to 5."""


class JudgeScoreResponse(BaseModel):
    """Single rubric score assigned by an LLM judge."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5, description="Integer rubric score from 1 (bad) to 5 (perfect).")


def judge_receipt_scan(
    model: BaseChatModel,
    raw_name: str,
    normalised_name: str,
    quantity: float,
    unit: str,
    unit_price: float | None,
) -> int:
    prompt = (
        f'Raw receipt item: "{raw_name}"\n'
        f'Normalised to: "{normalised_name}", quantity={quantity}{unit}, unit_price={unit_price}/{unit}'
    )
    response = invoke_structured(
        model,
        JudgeScoreResponse,
        [SystemMessage(content=RECEIPT_SCAN_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-receipt"}},
    )
    return response.score


def judge_suggestion(
    model: BaseChatModel,
    pantry_summary: str,
    dietary_flags: list[str],
    title: str,
    reason: str,
) -> int:
    prompt = (
        f"Pantry state:\n{pantry_summary}\n\n"
        f"Dietary flags: {dietary_flags}\n\n"
        f'Suggested recipe: "{title}"\n'
        f'Reason: "{reason}"'
    )
    response = invoke_structured(
        model,
        JudgeScoreResponse,
        [SystemMessage(content=SUGGESTIONS_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-meal-plan-generation"}},
    )
    return response.score


def judge_recipe_import(
    model: BaseChatModel,
    html_snippet: str,
    extracted_json: dict,
) -> int:
    prompt = (
        f"Source HTML (first 2000 chars):\n{html_snippet[:2000]}\n\n"
        f"Extracted recipe:\n{json.dumps(extracted_json, indent=2)}"
    )
    response = invoke_structured(
        model,
        JudgeScoreResponse,
        [SystemMessage(content=RECIPE_IMPORT_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-recipe-import"}},
    )
    return response.score


def judge_purchase_description(
    model: BaseChatModel,
    purchase_text: str,
    parsed_items: list[dict],
) -> int:
    prompt = f"Purchase description:\n{purchase_text}\n\n" f"Parsed pantry items:\n{json.dumps(parsed_items, indent=2)}"
    response = invoke_structured(
        model,
        JudgeScoreResponse,
        [SystemMessage(content=PURCHASE_DESCRIPTION_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-pantry-purchase-description"}},
    )
    return response.score


def judge_shopping_list_description(
    model: BaseChatModel,
    shopping_text: str,
    parsed_response: dict,
) -> int:
    prompt = (
        f"Shopping list description:\n{shopping_text}\n\n"
        f"Parsed shopping proposal:\n{json.dumps(parsed_response, indent=2)}"
    )
    response = invoke_structured(
        model,
        JudgeScoreResponse,
        [SystemMessage(content=SHOPPING_LIST_DESCRIPTION_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-shopping-list-description"}},
    )
    return response.score
