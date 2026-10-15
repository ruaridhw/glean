"""The five features under study: each one's rubric as a score question, and its judge prompt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.integration.evals.judges import rubrics

from judge_study.rubric_scale import rubric_score_question

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.decisions import ScoreQuestion
    from judge_study.results import FeatureName


@dataclass(frozen=True)
class FeatureSpec:
    label: str
    question: ScoreQuestion
    prompt: Callable[..., str]
    llm_judge: Callable[..., int]
    rubric: str


def _spec(label: str, rubric: str, prompt: Callable[..., str], llm_judge: Callable[..., int]) -> FeatureSpec:
    return FeatureSpec(label, rubric_score_question(rubric), prompt, llm_judge, rubric)


FEATURES: dict[FeatureName, FeatureSpec] = {
    "receipt_scan": _spec(
        "Receipt scan", rubrics.RECEIPT_SCAN_RUBRIC, rubrics.receipt_scan_prompt, rubrics.judge_receipt_scan
    ),
    "meal_plan": _spec("Meal plan", rubrics.MEAL_PLAN_RUBRIC, rubrics.meal_plan_prompt, rubrics.judge_meal_plan_recipe),
    "recipe_import": _spec(
        "Recipe import", rubrics.RECIPE_IMPORT_RUBRIC, rubrics.recipe_import_prompt, rubrics.judge_recipe_import
    ),
    "pantry_description": _spec(
        "Pantry description",
        rubrics.PURCHASE_DESCRIPTION_RUBRIC,
        rubrics.purchase_description_prompt,
        rubrics.judge_purchase_description,
    ),
    "shopping_list_description": _spec(
        "Shopping-list description",
        rubrics.SHOPPING_LIST_DESCRIPTION_RUBRIC,
        rubrics.shopping_list_description_prompt,
        rubrics.judge_shopping_list_description,
    ),
}
