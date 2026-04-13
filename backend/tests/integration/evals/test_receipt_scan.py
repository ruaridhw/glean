from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.receipts.schemas import ParsedIngredient
from glean.receipts.service import NORMALISE_SYSTEM_PROMPT

from .judges.rubrics import judge_receipt_scan

ALLOWED_UNITS = {"g", "ml", "units"}


def _invoke_receipt_scan(model: BaseChatModel, line_items: list[dict], *, example_idx: int) -> str:
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(line_items)),
        ],
        config={"metadata": {"feature": "eval-receipt-scan", "example_idx": example_idx}},
    )
    return result.content


class TestReceiptScanStructural:
    """Layer 1: Structural checks (hard gate). JSON + schema validation."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw, list), f"Example {i}: expected list, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            assert len(items) > 0, f"Example {i}: returned empty list"

    def test_all_items_have_valid_units(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                assert (
                    item.unit in ALLOWED_UNITS
                ), f"Example {i}: item '{item.name}' has unit '{item.unit}', expected one of {ALLOWED_UNITS}"

    def test_output_count_matches_input_count(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = json.loads(content)
            expected_count = len(example["input"]["line_items"])
            assert len(items) == expected_count, f"Example {i}: expected {expected_count} items, got {len(items)}"


@pytest.mark.soft_gate
class TestReceiptScanHeuristic:
    """Layer 2: Heuristic checks (soft gate). Deterministic quality checks."""

    def test_names_are_lowercase(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                if item.name != item.name.lower():
                    failures.append(f"Example {i}: '{item.name}' is not lowercase")
        assert not failures, "Lowercase check failures:\n" + "\n".join(failures)

    def test_no_common_abbreviations(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        abbreviations = {"bnls", "chkn", "whl", "org", "brst", "flts", "sml", "lrg", "med", "pck"}
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                words = set(item.name.lower().split())
                found = words & abbreviations
                if found:
                    failures.append(f"Example {i}: '{item.name}' contains abbreviations: {found}")
        assert not failures, "Abbreviation check failures:\n" + "\n".join(failures)

    def test_quantities_are_positive(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                if item.quantity <= 0:
                    failures.append(f"Example {i}: '{item.name}' has quantity {item.quantity}")
                if item.unit_price is not None and item.unit_price <= 0:
                    failures.append(f"Example {i}: '{item.name}' has unit_price {item.unit_price}")
        assert not failures, "Positive quantity check failures:\n" + "\n".join(failures)

    def test_confidence_in_range(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                if not (0.0 <= item.confidence <= 1.0):
                    failures.append(f"Example {i}: '{item.name}' has confidence {item.confidence}")
        assert not failures, "Confidence range check failures:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestReceiptScanJudge:
    """Layer 3: LLM-as-judge (soft gate). Quality scoring via rubric."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(receipt_scan_dataset):
            content = _invoke_receipt_scan(eval_model, example["input"]["line_items"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item, raw_input in zip(items, example["input"]["line_items"], strict=True):
                score = judge_receipt_scan(
                    model=judge_model,
                    raw_name=raw_input["name"],
                    normalised_name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    unit_price=item.unit_price,
                )
                scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
