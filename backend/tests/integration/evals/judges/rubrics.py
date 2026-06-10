from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

RECEIPT_SCAN_RUBRIC = """You are evaluating a grocery receipt normalisation system.
Given a raw receipt line item name and the system's normalised output, rate the quality 1-5:

5 = Perfect canonical name, correct unit conversion, accurate price calculation
4 = Minor issue (slightly verbose name, small rounding difference)
3 = Acceptable but imprecise (name has extra words, unit roughly correct)
2 = Significant error (wrong unit type, major quantity error)
1 = Wrong (completely misidentified item)

Respond with ONLY a single integer 1-5. No explanation."""

MEAL_PLAN_RUBRIC = """You are evaluating a meal-plan generation system.
Given a user's pantry state, dietary flags, and the generated meal-plan recipe, rate the quality 1-5:

5 = Excellent — uses expiring/urgent pantry items, reason is specific and references actual pantry data
4 = Good — reasonable recipe, reason references pantry items by name
3 = Acceptable — valid recipe but reason is generic (e.g. "good for dinner")
2 = Poor — ignores pantry priorities or reason is vague/irrelevant
1 = Bad — violates dietary flags or completely irrelevant to pantry state

Respond with ONLY a single integer 1-5. No explanation."""

RECIPE_IMPORT_RUBRIC = """You are evaluating a recipe extraction system.
Given source HTML and the system's extracted recipe JSON, rate the extraction quality 1-5:

5 = Perfect — all fields accurately captured from the HTML
4 = Minor omission (missing optional field like cuisine or difficulty)
3 = Mostly correct but missing some ingredients or instruction steps
2 = Significant errors (wrong title, missing most ingredients)
1 = Completely wrong extraction

Respond with ONLY a single integer 1-5. No explanation."""


def _parse_score(content: str) -> int:
    """Extract integer score from LLM response, defaulting to 1 if unparsable."""
    match = re.search(r"[1-5]", content)
    return int(match.group()) if match else 1


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
    result = model.invoke(
        [SystemMessage(content=RECEIPT_SCAN_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-receipt"}},
    )
    return _parse_score(result.content)


def judge_meal_plan_recipe(
    model: BaseChatModel,
    pantry_summary: str,
    dietary_flags: list[str],
    title: str,
    reason: str,
) -> int:
    prompt = (
        f"Pantry state:\n{pantry_summary}\n\n"
        f"Dietary flags: {dietary_flags}\n\n"
        f'Meal-plan recipe: "{title}"\n'
        f'Reason: "{reason}"'
    )
    result = model.invoke(
        [SystemMessage(content=MEAL_PLAN_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-meal-plan-generation"}},
    )
    return _parse_score(result.content)


def judge_recipe_import(
    model: BaseChatModel,
    html_snippet: str,
    extracted_json: dict,
) -> int:
    prompt = (
        f"Source HTML (first 2000 chars):\n{html_snippet[:2000]}\n\n"
        f"Extracted recipe:\n{json.dumps(extracted_json, indent=2)}"
    )
    result = model.invoke(
        [SystemMessage(content=RECIPE_IMPORT_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-recipe-import"}},
    )
    return _parse_score(result.content)
