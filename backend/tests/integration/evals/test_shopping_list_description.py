from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.shopping.schemas import ShoppingParseResponse
from glean.shopping.service import SHOPPING_PARSE_SYSTEM_PROMPT

from .judges.rubrics import judge_shopping_list_description

ALLOWED_UNITS = {"g", "ml", "units", "pack", "bottle", "bag", "box"}


def _invoke_shopping_list_description(model: BaseChatModel, text: str, *, example_idx: int) -> str:
    result = model.invoke(
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {text}"),
        ],
        config={"metadata": {"feature": "eval-shopping-list-description", "example_idx": example_idx}},
    )
    return result.content


class TestShoppingListDescriptionStructural:
    def test_all_examples_return_valid_json_object(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw, dict), f"Example {i}: expected object, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            response = ShoppingParseResponse(**json.loads(content))
            assert len(response.items) == example["expected"]["count"], f"Example {i}: returned {len(response.items)}"

    def test_clarifying_questions_are_list_of_strings(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            response = ShoppingParseResponse(**json.loads(content))
            assert all(isinstance(q, str) for q in response.clarifying_questions), f"Example {i}: invalid questions"


@pytest.mark.soft_gate
class TestShoppingListDescriptionHeuristic:
    def test_expected_names_are_present(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(shopping_list_description_dataset):
            expected_names = set(example["expected"]["names"])
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            response = ShoppingParseResponse(**json.loads(content))
            actual_names = {item.name for item in response.items}
            missing = expected_names - actual_names
            if missing:
                failures.append(f"Example {i}: missing names {sorted(missing)} from {sorted(actual_names)}")
        assert not failures, "Expected-name check failures:\n" + "\n".join(failures)

    def test_units_quantities_and_confidence_are_valid(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(shopping_list_description_dataset):
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            response = ShoppingParseResponse(**json.loads(content))
            for item in response.items:
                if item.unit not in ALLOWED_UNITS:
                    failures.append(f"Example {i}: '{item.name}' has invalid unit '{item.unit}'")
                if item.quantity <= 0:
                    failures.append(f"Example {i}: '{item.name}' has quantity {item.quantity}")
                if not (0.0 <= item.confidence <= 1.0):
                    failures.append(f"Example {i}: '{item.name}' has confidence {item.confidence}")
        assert not failures, "Unit/quantity/confidence check failures:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestShoppingListDescriptionJudge:
    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(shopping_list_description_dataset):
            content = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            response = ShoppingParseResponse(**json.loads(content))
            score = judge_shopping_list_description(
                model=judge_model,
                shopping_text=example["input"]["text"],
                parsed_response=response.model_dump(),
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
