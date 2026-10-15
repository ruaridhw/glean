"""Deliberately degraded copies of production outputs.

Production outputs nearly all earn a 5, which leaves nothing for the judges to disagree about. A degraded copy of
each one gives the study low scores too. Even-numbered outputs get a moderate fault, odd-numbered a severe one.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from judge_study.results import OutputItem

_WRONG_ITEM = "bin bags"


def _receipt(inputs: dict[str, Any], severe: bool) -> dict[str, Any]:
    if severe:
        return {**inputs, "normalised_name": _WRONG_ITEM}
    return {**inputs, "quantity": inputs["quantity"] * 10, "unit": "units"}


def _meal_plan(inputs: dict[str, Any], severe: bool) -> dict[str, Any]:
    if severe:
        return {**inputs, "title": "Beef wellington", "reason": "A showstopper dinner."}
    return {**inputs, "reason": "Good for dinner."}


def _recipe_import(inputs: dict[str, Any], severe: bool) -> dict[str, Any]:
    extracted = copy.deepcopy(inputs["extracted_json"])
    if severe:
        extracted.update(title="Untitled", ingredients=[], instructions=[])
    else:
        extracted["ingredients"] = extracted["ingredients"][: max(1, len(extracted["ingredients"]) // 2)]
    return {**inputs, "extracted_json": extracted}


def _pantry_description(inputs: dict[str, Any], severe: bool) -> dict[str, Any]:
    parsed = copy.deepcopy(inputs["parsed_items"])
    if severe:
        parsed = [{"name": "caviar", "quantity": 500, "unit": "g"}]
    else:
        parsed = parsed[:-1] or [{"name": "caviar", "quantity": 500, "unit": "g"}]
    return {**inputs, "parsed_items": parsed}


def _shopping_list_description(inputs: dict[str, Any], severe: bool) -> dict[str, Any]:
    response = copy.deepcopy(inputs["parsed_response"])
    invented = {"name": "caviar", "quantity": 500, "unit": "g"}
    response["items"] = [invented] if severe else [*response["items"][:-1], invented]
    return {**inputs, "parsed_response": response}


_DEGRADE = {
    "receipt_scan": _receipt,
    "meal_plan": _meal_plan,
    "recipe_import": _recipe_import,
    "pantry_description": _pantry_description,
    "shopping_list_description": _shopping_list_description,
}

# How each feature's displayed output follows its degraded judge inputs.
_OUTPUT_FROM = {
    "receipt_scan": lambda inputs, shown: {
        **shown,
        "name": inputs["normalised_name"],
        "quantity": inputs["quantity"],
        "unit": inputs["unit"],
    },
    "meal_plan": lambda inputs, shown: {**shown, "title": inputs["title"], "reason": inputs["reason"]},
    "recipe_import": lambda inputs, shown: inputs["extracted_json"],
    "pantry_description": lambda inputs, shown: {"items": inputs["parsed_items"]},
    "shopping_list_description": lambda inputs, shown: inputs["parsed_response"],
}


def stress_variant(item: OutputItem) -> OutputItem:
    severe = int(item.item_id.rsplit("/", 1)[-1]) % 2 == 1
    judge_inputs = _DEGRADE[item.feature](item.judge_inputs, severe)
    return item.model_copy(
        update={
            "item_id": f"{item.item_id}+stress",
            "origin": "stress",
            "judge_inputs": judge_inputs,
            "output": _OUTPUT_FROM[item.feature](judge_inputs, item.output),
            "judgements": [],
            "human_score": None,
        }
    )
