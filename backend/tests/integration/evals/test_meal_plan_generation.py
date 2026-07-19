from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import invoke_structured
from glean.meal_plan.schemas import MealPlanResponse
from glean.meal_plan.service import MEAL_PLAN_SYSTEM_PROMPT

from .judges.rubrics import judge_meal_plan_recipe


def _invoke_meal_plan_generation(
    model: BaseChatModel, input_data: dict[str, Any], *, example_idx: int
) -> MealPlanResponse:
    context = json.dumps(input_data, default=str)
    return invoke_structured(
        model,
        MealPlanResponse,
        [
            SystemMessage(content=MEAL_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ],
        config={"metadata": {"feature": "eval-meal-plan-generation", "example_idx": example_idx}},
    )


class TestMealPlanGenerationStructural:
    """Layer 1: Structural checks (hard gate)."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(meal_plan_generation_dataset):
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            assert isinstance(response, MealPlanResponse), f"Example {i}: expected MealPlanResponse"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(meal_plan_generation_dataset):
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            assert len(response.suggestions) > 0, f"Example {i}: returned empty list"

    @pytest.mark.xfail(
        reason=(
            "qwen/qwen3.7-plus (the meal-plan-generation production model) does not respect "
            "meals_per_week in-prompt: it returns more than the limit (observed 6 for a limit "
            "of 2) even with an explicit 'Return AT MOST meals_per_week ... never exceed' rule. "
            "The /meal-plan service therefore enforces the cap by truncating to "
            "request.meals_per_week (see meal_plan.service.generate_meal_plan and "
            "tests/meal_plan/test_router.py::test_generate_meal_plan_truncates_to_meals_per_week), "
            "so production output is always within the limit. Kept as a raw-model adherence "
            "signal; will xpass if a future model complies."
        ),
        strict=False,
    )
    def test_meal_plan_count_within_limit(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(meal_plan_generation_dataset):
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            limit = example["input"]["meals_per_week"]
            assert len(response.suggestions) <= limit, (
                f"Example {i}: got {len(response.suggestions)} meals, limit is {limit}"
            )

    def test_recipe_ids_are_integers(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(meal_plan_generation_dataset):
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            for recipe in response.suggestions:
                assert isinstance(recipe.recipe_id, int), f"Example {i}: recipe_id {recipe.recipe_id} is not an int"


@pytest.mark.soft_gate
class TestMealPlanGenerationHeuristic:
    """Layer 2: Heuristic checks (soft gate)."""

    def test_missing_ingredients_not_in_pantry(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(meal_plan_generation_dataset):
            pantry_names = {item["name"].lower() for item in example["input"]["pantry"]}
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            for recipe in response.suggestions:
                overlap = {ing.lower() for ing in recipe.missing_ingredients} & pantry_names
                if overlap:
                    failures.append(f"Example {i}: '{recipe.title}' lists {overlap} as missing but they're in pantry")
        assert not failures, "Missing ingredients check:\n" + "\n".join(failures)

    def test_recipe_ids_reference_known_recipes(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(meal_plan_generation_dataset):
            known_ids = {r["recipe_id"] for r in example["input"]["recipe_history"]}
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            for recipe in response.suggestions:
                if recipe.recipe_id not in known_ids:
                    failures.append(
                        f"Example {i}: recipe_id {recipe.recipe_id} ('{recipe.title}') not in input history {known_ids}"
                    )
        assert not failures, "Recipe ID reference check:\n" + "\n".join(failures)

    def test_reasons_are_substantive(
        self,
        eval_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(meal_plan_generation_dataset):
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            for recipe in response.suggestions:
                if len(recipe.reason) < 10:
                    failures.append(
                        f"Example {i}: '{recipe.title}' reason too short ({len(recipe.reason)} chars): "
                        f"'{recipe.reason}'"
                    )
        assert not failures, "Reason length check:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestMealPlanGenerationJudge:
    """Layer 3: LLM-as-judge (soft gate)."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        meal_plan_generation_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(meal_plan_generation_dataset):
            pantry_summary = "\n".join(
                f"- {p['name']}: {p['quantity']}{p['unit']} (urgency: {p['urgency_score']})"
                for p in example["input"]["pantry"]
            )
            response = _invoke_meal_plan_generation(eval_model, example["input"], example_idx=i)
            for recipe in response.suggestions:
                score = judge_meal_plan_recipe(
                    model=judge_model,
                    pantry_summary=pantry_summary,
                    dietary_flags=example["input"]["dietary_flags"],
                    title=recipe.title,
                    reason=recipe.reason,
                )
                scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
