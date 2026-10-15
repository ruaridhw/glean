from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import Feature, invoke_structured
from glean.shopping.schemas import ShoppingParseResponse, ShoppingUnit
from glean.shopping.service import SHOPPING_PARSE_SYSTEM_PROMPT

from .judges.rubrics import judge_shopping_list_description

FEATURE = Feature.SHOPPING_LIST_DESCRIPTION

ALLOWED_UNITS = {unit.value for unit in ShoppingUnit}


def _invoke_shopping_list_description(model: BaseChatModel, text: str, *, example_idx: int) -> ShoppingParseResponse:
    return invoke_structured(
        model,
        ShoppingParseResponse,
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {text}"),
        ],
        config={"metadata": {"feature": "eval-shopping-list-description", "example_idx": example_idx}},
    )


class TestShoppingListDescriptionStructural:
    def test_all_examples_return_valid_json_object(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            assert isinstance(response, ShoppingParseResponse), f"Example {i}: expected ShoppingParseResponse"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            assert len(response.items) == example["expected"]["count"], f"Example {i}: returned {len(response.items)}"

    def test_clarifying_questions_are_list_of_strings(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            assert all(isinstance(q, str) for q in response.clarifying_questions), f"Example {i}: invalid questions"


DISH_ONLY_INPUTS = ["tacos", "stuff for a roast dinner"]


class TestShoppingListDescriptionDishNames:
    def test_dish_names_expand_to_low_confidence_items(self, eval_model: BaseChatModel) -> None:
        for i, text in enumerate(DISH_ONLY_INPUTS):
            response = _invoke_shopping_list_description(eval_model, text, example_idx=100 + i)
            assert len(response.items) >= 2, f"{text!r}: expected ingredient proposals, got {response.items}"
            assert all(item.confidence <= 0.6 for item in response.items), f"{text!r}: confidence too high"


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
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
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
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            for item in response.items:
                if item.unit_price is not None:
                    failures.append(f"Example {i}: '{item.name}' has unit_price {item.unit_price}")
                if item.unit not in ALLOWED_UNITS:
                    failures.append(f"Example {i}: '{item.name}' has invalid unit '{item.unit}'")
                if item.quantity <= 0:
                    failures.append(f"Example {i}: '{item.name}' has quantity {item.quantity}")
                if not (0.0 <= item.confidence <= 1.0):
                    failures.append(f"Example {i}: '{item.name}' has confidence {item.confidence}")
        assert not failures, "Unit/quantity/confidence check failures:\n" + "\n".join(failures)


def _find_item(response: ShoppingParseResponse, expected_name: str) -> Any:
    return next((item for item in response.items if expected_name in item.name.lower()), None)


VAGUE_INPUTS = ["some snacks", "something for lunch"]


@pytest.mark.soft_gate
class TestShoppingListDescriptionExpectations:
    """Expectations written from the input text, independent of the prompt and the schema."""

    def test_quantities_and_units_match_what_the_text_says(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(shopping_list_description_dataset):
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            for name, (quantity, unit) in example["expected"]["items"].items():
                item = _find_item(response, name)
                if item is None:
                    failures.append(f"Example {i}: no item matching {name!r} in {[x.name for x in response.items]}")
                elif (item.quantity, item.unit.value) != (quantity, unit):
                    failures.append(
                        f"Example {i}: {name!r} got {item.quantity} {item.unit.value}, want {quantity} {unit}"
                    )
        assert not failures, "Quantity/unit failures:\n" + "\n".join(failures)

    def test_clarifying_questions_only_appear_when_the_text_is_ambiguous(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(shopping_list_description_dataset):
            limit = example["expected"]["max_clarifying_questions"]
            if limit is None:
                continue
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            if len(response.clarifying_questions) > limit:
                failures.append(f"Example {i}: asked {response.clarifying_questions} for a clear list")
        assert not failures, "Unneeded clarifying questions:\n" + "\n".join(failures)

    def test_vague_requests_still_propose_items_with_low_confidence(self, eval_model: BaseChatModel) -> None:
        for i, text in enumerate(VAGUE_INPUTS):
            response = _invoke_shopping_list_description(eval_model, text, example_idx=200 + i)
            assert response.items, f"{text!r}: no items proposed"
            assert all(item.confidence <= 0.7 for item in response.items), f"{text!r}: overconfident {response.items}"

    def test_deprecated_fields_stay_null(
        self,
        eval_model: BaseChatModel,
        shopping_list_description_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(shopping_list_description_dataset):
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            dumped = response.model_dump()["items"]
            assert all(item["unit_price"] is None and item["api_ingredient_id"] is None for item in dumped)


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
            response = _invoke_shopping_list_description(eval_model, example["input"]["text"], example_idx=i)
            score = judge_shopping_list_description(
                model=judge_model,
                shopping_text=example["input"]["text"],
                parsed_response=response.model_dump(),
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
