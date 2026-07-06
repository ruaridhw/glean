from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.suggestions.schemas import SuggestedRecipe
from glean.suggestions.service import SUGGESTION_SYSTEM_PROMPT

from .judges.rubrics import judge_suggestion


def _invoke_suggestions(model: BaseChatModel, input_data: dict[str, Any], *, example_idx: int) -> str:
    context = json.dumps(input_data, default=str)
    result = model.invoke(
        [
            SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ],
        config={"metadata": {"feature": "eval-meal-plan-generation", "example_idx": example_idx}},
    )
    return result.content


class TestSuggestionsStructural:
    """Layer 1: Structural checks (hard gate)."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw, list), f"Example {i}: expected list, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            raw = json.loads(content)
            suggestions = [SuggestedRecipe(**item) for item in raw]
            assert len(suggestions) > 0, f"Example {i}: returned empty list"

    def test_suggestion_count_within_limit(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            suggestions = json.loads(content)
            limit = example["input"]["meals_per_week"]
            assert len(suggestions) <= limit, f"Example {i}: got {len(suggestions)} suggestions, limit is {limit}"

    def test_recipe_ids_are_integers(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            for item in json.loads(content):
                assert isinstance(item["recipe_id"], int), f"Example {i}: recipe_id {item['recipe_id']} is not an int"


@pytest.mark.soft_gate
class TestSuggestionsHeuristic:
    """Layer 2: Heuristic checks (soft gate)."""

    def test_missing_ingredients_not_in_pantry(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            pantry_names = {item["name"].lower() for item in example["input"]["pantry"]}
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            suggestions = [SuggestedRecipe(**item) for item in json.loads(content)]
            for s in suggestions:
                overlap = {ing.lower() for ing in s.missing_ingredients} & pantry_names
                if overlap:
                    failures.append(f"Example {i}: '{s.title}' lists {overlap} as missing but they're in pantry")
        assert not failures, "Missing ingredients check:\n" + "\n".join(failures)

    def test_recipe_ids_reference_known_recipes(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            known_ids = {r["recipe_id"] for r in example["input"]["recipe_history"]}
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            suggestions = [SuggestedRecipe(**item) for item in json.loads(content)]
            for s in suggestions:
                if s.recipe_id not in known_ids:
                    failures.append(
                        f"Example {i}: recipe_id {s.recipe_id} ('{s.title}') not in input history {known_ids}"
                    )
        assert not failures, "Recipe ID reference check:\n" + "\n".join(failures)

    def test_reasons_are_substantive(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            suggestions = [SuggestedRecipe(**item) for item in json.loads(content)]
            for s in suggestions:
                if len(s.reason) < 10:
                    failures.append(f"Example {i}: '{s.title}' reason too short ({len(s.reason)} chars): '{s.reason}'")
        assert not failures, "Reason length check:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestSuggestionsJudge:
    """Layer 3: LLM-as-judge (soft gate)."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(suggestions_dataset):
            pantry_summary = "\n".join(
                f"- {p['name']}: {p['quantity']}{p['unit']} (urgency: {p['urgency_score']})"
                for p in example["input"]["pantry"]
            )
            content = _invoke_suggestions(eval_model, example["input"], example_idx=i)
            suggestions = [SuggestedRecipe(**item) for item in json.loads(content)]
            for s in suggestions:
                score = judge_suggestion(
                    model=judge_model,
                    pantry_summary=pantry_summary,
                    dietary_flags=example["input"]["dietary_flags"],
                    title=s.title,
                    reason=s.reason,
                )
                scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
