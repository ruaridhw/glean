"""Freeze each feature's production output, so every judge scores exactly the same thing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from judge_study.results import OutputItem

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from judge_study.results import FeatureName


def _item(feature: FeatureName, example: int, index: int, **fields: Any) -> OutputItem:
    return OutputItem(item_id=f"{feature}/{example}/{index}", feature=feature, **fields)


def _receipt_scan(i: int, example: dict[str, Any], response: Any) -> list[OutputItem]:
    lines = example["input"]["line_items"]
    if len(response.items) != len(lines):
        raise ValueError(f"Example {i} has {len(lines)} line items but the scan returned {len(response.items)}")
    return [
        _item(
            "receipt_scan",
            i,
            k,
            input=line,
            output=parsed.model_dump(),
            judge_inputs={
                "raw_name": line["name"],
                "normalised_name": parsed.name,
                "quantity": parsed.quantity,
                "unit": parsed.unit,
                "unit_price": parsed.unit_price,
            },
        )
        for k, (line, parsed) in enumerate(zip(lines, response.items, strict=True))
    ]


def _meal_plan(i: int, example: dict[str, Any], response: Any) -> list[OutputItem]:
    request = example["input"]
    pantry_summary = "\n".join(
        f"- {p['name']}: {p['quantity']}{p['unit']} (urgency: {p['urgency_score']})" for p in request["pantry"]
    )
    return [
        _item(
            "meal_plan",
            i,
            k,
            input={"pantry": pantry_summary, "dietary_flags": request["dietary_flags"]},
            output=recipe.model_dump(),
            judge_inputs={
                "pantry_summary": pantry_summary,
                "dietary_flags": request["dietary_flags"],
                "title": recipe.title,
                "reason": recipe.reason,
            },
        )
        for k, recipe in enumerate(response.suggestions)
    ]


def _recipe_import(i: int, example: dict[str, Any], response: Any) -> list[OutputItem]:
    html = example["input"]["html"]
    extracted = response.model_dump(by_alias=True)
    return [
        _item(
            "recipe_import",
            i,
            0,
            input={"html": html},
            output=extracted,
            judge_inputs={"html_snippet": html, "extracted_json": extracted},
        )
    ]


def _pantry_description(i: int, example: dict[str, Any], response: Any) -> list[OutputItem]:
    text = example["input"]["text"]
    parsed = [item.model_dump() for item in response.items]
    return [
        _item(
            "pantry_description",
            i,
            0,
            input={"text": text},
            output={"items": parsed},
            judge_inputs={"purchase_text": text, "parsed_items": parsed},
        )
    ]


def _shopping_list_description(i: int, example: dict[str, Any], response: Any) -> list[OutputItem]:
    text = example["input"]["text"]
    parsed = response.model_dump()
    return [
        _item(
            "shopping_list_description",
            i,
            0,
            input={"text": text},
            output=parsed,
            judge_inputs={"shopping_text": text, "parsed_response": parsed},
        )
    ]


_EXPLODERS: dict[str, Callable[[int, dict[str, Any], Any], list[OutputItem]]] = {
    "receipt_scan": _receipt_scan,
    "meal_plan": _meal_plan,
    "recipe_import": _recipe_import,
    "pantry_description": _pantry_description,
    "shopping_list_description": _shopping_list_description,
}


def freeze_feature(
    feature: FeatureName,
    examples: list[dict[str, Any]],
    invoke: Callable[[int, dict[str, Any]], BaseModel],
) -> list[OutputItem]:
    """Run the production prompt once per fixture example and keep what each judge will be asked about."""
    items: list[OutputItem] = []
    for index, example in enumerate(examples):
        items.extend(_EXPLODERS[feature](index, example, invoke(index, example)))
    return items
