from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import Feature, invoke_structured
from glean.meal_plan.schemas import MealPlanRequest, MealPlanResponse
from glean.observability import logger, tracer

MEAL_PLAN_SYSTEM_PROMPT = """You are a meal planning assistant for the Glean app.
Given a user's pantry, recipe history, and preferences, choose meals to cook this week.

Rules:
- Prioritise recipes that use pantry items with high urgency scores (expiring soon, unused long)
- Balance food group coverage across the week
- Respect dietary flags (never choose recipes incompatible with user's dietary_flags)
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Prefer recipes not cooked recently (further last_cooked_at = higher priority)
- Return AT MOST meals_per_week planned meals — never exceed meals_per_week. Returning fewer is
  fine; do not pad the list with weaker choices to reach the limit."""


@tracer.capture_method
def generate_meal_plan(request: MealPlanRequest, *, model: BaseChatModel) -> MealPlanResponse:

    context = {
        "pantry": [item.model_dump() for item in request.pantry],
        "recipe_history": [r.model_dump(mode="json") for r in request.recipe_history],
        "food_group_coverage_this_week": request.food_group_coverage,
        "purchase_tolerance": request.purchase_tolerance,
        "meals_per_week": request.meals_per_week,
        "dietary_flags": request.dietary_flags,
        "max_active_time_mins": request.max_active_time_mins,
    }

    logger.info(
        "generating meal plan",
        extra={
            "pantry_items": len(request.pantry),
            "recipes": len(request.recipe_history),
        },
    )

    response = invoke_structured(
        model,
        MealPlanResponse,
        [
            SystemMessage(content=MEAL_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ],
        config={"metadata": {"feature": Feature.MEAL_PLAN_GENERATION}},
    )

    # Enforce the count cap server-side: the prompt asks for at most meals_per_week, but
    # models (especially reasoning models) do not always comply, so guarantee the contract
    # regardless of model behaviour rather than surfacing an over-long plan to the client.
    if len(response.suggestions) > request.meals_per_week:
        logger.error(
            "meal plan exceeded meals_per_week; truncating",
            extra={"returned": len(response.suggestions), "limit": request.meals_per_week},
        )
        response = response.model_copy(update={"suggestions": response.suggestions[: request.meals_per_week]})

    logger.info("meal plan generated", extra={"count": len(response.suggestions)})
    return response
