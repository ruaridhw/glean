from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from glean.llm import Feature, invoke_structured
from glean.observability import logger, tracer
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse

SUGGESTION_SYSTEM_PROMPT = """You are a meal planning assistant for the Glean app.
Given a user's pantry, recipe history, and preferences, suggest meals to cook this week.

Rules:
- Prioritise recipes that use pantry items with high urgency scores (expiring soon, unused long)
- Balance food group coverage across the week
- Respect dietary flags (never suggest recipes incompatible with user's dietary_flags)
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Prefer recipes not cooked recently (further last_cooked_at = higher priority)
- Return up to meals_per_week suggestions

Respond with structured data containing a suggestions array of objects:
{
  "suggestions": [
    {
      "recipe_id": <int>,
      "title": <str>,
      "reason": <str>,
      "missing_ingredients": [<ingredient names not in pantry>]
    }
  ]
}"""


@tracer.capture_method
def get_suggestions(request: SuggestionRequest, *, model: BaseChatModel) -> SuggestionResponse:

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
        "requesting suggestions",
        extra={
            "pantry_items": len(request.pantry),
            "recipes": len(request.recipe_history),
        },
    )

    response = invoke_structured(
        model,
        SuggestionResponse,
        [
            SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ],
        config={"metadata": {"feature": Feature.MEAL_PLAN_GENERATION}},
    )
    logger.info("suggestions received", extra={"count": len(response.suggestions)})
    return response
