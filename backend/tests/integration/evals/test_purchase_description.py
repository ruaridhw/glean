from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.receipts.schemas import ParsedIngredient
from glean.receipts.service import NORMALISE_SYSTEM_PROMPT

from .judges.rubrics import judge_purchase_description

ALLOWED_UNITS = {"g", "ml", "units"}


def _invoke_purchase_description(model: BaseChatModel, text: str, *, example_idx: int) -> str:
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {text}"),
        ],
        config={"metadata": {"feature": "eval-pantry-purchase-description", "example_idx": example_idx}},
    )
    return result.content


class TestPurchaseDescriptionStructural:
    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(purchase_description_dataset):
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw, list), f"Example {i}: expected list, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(purchase_description_dataset):
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            assert len(items) == example["expected"]["count"], f"Example {i}: returned {len(items)} items"

    def test_all_items_have_valid_units(
        self,
        eval_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(purchase_description_dataset):
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                assert item.unit in ALLOWED_UNITS, f"Example {i}: '{item.name}' has invalid unit '{item.unit}'"


@pytest.mark.soft_gate
class TestPurchaseDescriptionHeuristic:
    def test_expected_names_are_present(
        self,
        eval_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(purchase_description_dataset):
            expected_names = set(example["expected"]["names"])
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            actual_names = {ParsedIngredient(**item).name for item in json.loads(content)}
            missing = expected_names - actual_names
            if missing:
                failures.append(f"Example {i}: missing names {sorted(missing)} from {sorted(actual_names)}")
        assert not failures, "Expected-name check failures:\n" + "\n".join(failures)

    def test_quantities_and_confidence_are_valid(
        self,
        eval_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(purchase_description_dataset):
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            for item in items:
                if item.quantity <= 0:
                    failures.append(f"Example {i}: '{item.name}' has quantity {item.quantity}")
                if not (0.0 <= item.confidence <= 1.0):
                    failures.append(f"Example {i}: '{item.name}' has confidence {item.confidence}")
        assert not failures, "Quantity/confidence check failures:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestPurchaseDescriptionJudge:
    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        purchase_description_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(purchase_description_dataset):
            content = _invoke_purchase_description(eval_model, example["input"]["text"], example_idx=i)
            items = [ParsedIngredient(**item) for item in json.loads(content)]
            score = judge_purchase_description(
                model=judge_model,
                purchase_text=example["input"]["text"],
                parsed_items=[item.model_dump() for item in items],
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
