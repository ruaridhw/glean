from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.llm import Feature
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.schemas import (
    CorpusMealPlanResponse,
    MealPlanRequest,
    MealPlanResponse,
    MealPlanResult,
    MealPlanSuggestion,
)
from glean.observability import logger, tracer
from glean.recipes.corpus import RecipeCorpusStore

if TYPE_CHECKING:
    from glean.llm import LLMRouter

MEAL_PLAN_SYSTEM_PROMPT = """You are a meal planning assistant for the Glean app.
Given a user's pantry, recipe history, and preferences, choose meals to cook this week.

Rules:
- Only choose recipes from recipe_history, and copy each chosen recipe's recipe_id and title exactly.
  Never invent recipes or IDs; if no saved recipe fits, return fewer meals (or none).
- Prioritise recipes that use pantry items with high urgency scores (expiring soon, unused long)
- Balance food group coverage across the week
- Respect dietary flags (never choose recipes incompatible with user's dietary_flags)
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Prefer recipes not cooked recently (further last_cooked_at = higher priority)
- Return AT MOST meals_per_week planned meals — never exceed meals_per_week. Returning fewer is
  fine; do not pad the list with weaker choices to reach the limit."""

CORPUS_MEAL_PLAN_SYSTEM_PROMPT = """You are a meal planning assistant for the Glean app.
Choose dinners to cook this week from the candidate recipes provided.

Rules:
- Only choose from candidates, and copy each chosen recipe's external_id and title exactly.
  Never invent recipes or IDs.
- Prioritise candidates that use pantry items, especially those with high urgency scores
- Respect dietary_flags by checking each candidate's ingredients; skip any candidate that conflicts
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Vary cuisines and main ingredients across the week
- Return AT MOST meals_per_week planned meals — never exceed meals_per_week. Returning fewer is
  fine; do not pad the list with weaker choices to reach the limit."""

_MAX_CANDIDATE_INGREDIENTS = 12
_rng = random.Random()  # noqa: S311 - varies recipe sampling; not security-sensitive


@tracer.capture_method
def generate_meal_plan(
    request: MealPlanRequest,
    *,
    llm_router: LLMRouter,
    corpus: RecipeCorpusStore | None = None,
    rng: random.Random | None = None,
) -> MealPlanResult:
    if request.source == "corpus":
        return _generate_from_corpus(
            request, llm_router=llm_router, corpus=corpus or RecipeCorpusStore(), rng=rng or _rng
        )
    return _generate_from_saved(request, llm_router=llm_router)


def _generate_from_saved(request: MealPlanRequest, *, llm_router: LLMRouter) -> MealPlanResult:

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

    response = llm_router.invoke(
        Feature.MEAL_PLAN_GENERATION,
        MealPlanResponse,
        [
            SystemMessage(content=MEAL_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ],
    )

    # The app can only plan recipes the user has saved, so drop anything the model invented.
    known_ids = {recipe.recipe_id for recipe in request.recipe_history}
    unknown = [s.recipe_id for s in response.suggestions if s.recipe_id not in known_ids]
    if unknown:
        logger.error("meal plan suggested recipes outside recipe_history; dropping", extra={"recipe_ids": unknown})
        response = response.model_copy(
            update={"suggestions": [s for s in response.suggestions if s.recipe_id in known_ids]}
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
    return MealPlanResult(
        suggestions=[MealPlanSuggestion(**suggestion.model_dump()) for suggestion in response.suggestions]
    )


def _generate_from_corpus(
    request: MealPlanRequest, *, llm_router: LLMRouter, corpus: RecipeCorpusStore, rng: random.Random
) -> MealPlanResult:
    candidates = sample_corpus_candidates(
        corpus,
        pantry_names=[item.name for item in request.pantry],
        dietary_flags=request.dietary_flags,
        max_total_time_mins=request.max_active_time_mins,
        exclude_external_ids=request.exclude_external_ids,
        rng=rng,
    )
    logger.info(
        "generating corpus meal plan",
        extra={"pantry_items": len(request.pantry), "candidates": len(candidates)},
    )
    if not candidates:
        return MealPlanResult(suggestions=[])

    context = {
        "pantry": [item.model_dump() for item in request.pantry],
        "candidates": [
            {
                "external_id": candidate.external_id,
                "title": candidate.title,
                "cuisine": candidate.cuisine,
                "total_time_mins": candidate.total_time_mins,
                "ingredients": candidate.ingredient_names[:_MAX_CANDIDATE_INGREDIENTS],
            }
            for candidate in candidates
        ],
        "purchase_tolerance": request.purchase_tolerance,
        "meals_per_week": request.meals_per_week,
        "dietary_flags": request.dietary_flags,
    }
    response = llm_router.invoke(
        Feature.MEAL_PLAN_GENERATION,
        CorpusMealPlanResponse,
        [
            SystemMessage(content=CORPUS_MEAL_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ],
    )

    offered = {candidate.external_id for candidate in candidates}
    chosen = [suggestion for suggestion in response.suggestions if suggestion.external_id in offered]
    if len(chosen) < len(response.suggestions):
        logger.error(
            "corpus meal plan chose recipes that were not offered; dropping",
            extra={"external_ids": [s.external_id for s in response.suggestions if s.external_id not in offered]},
        )
    chosen = chosen[: request.meals_per_week]

    logger.info("meal plan generated", extra={"count": len(chosen)})
    return MealPlanResult(suggestions=[MealPlanSuggestion(**suggestion.model_dump()) for suggestion in chosen])
