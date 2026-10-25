from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

from glean.llm import Feature
from glean.meal_plan import pipeline
from glean.meal_plan.feedback import ScreenedFeedback, screen_feedback, without_note
from glean.meal_plan.schemas import (
    MealPlanRequest,
    MealPlanResponse,
    MealPlanResult,
    MealPlanSuggestion,
)
from glean.observability import logger, tracer
from glean.recipes.corpus import RecipeCorpusStore

if TYPE_CHECKING:
    from datetime import datetime

    from glean.decisions import DecisionClient
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

_rng = random.Random()  # noqa: S311 - varies recipe sampling; not security-sensitive


def generate_meal_plan(
    request: MealPlanRequest,
    *,
    llm_router: LLMRouter,
    decision_client: DecisionClient | None = None,
    corpus: RecipeCorpusStore | None = None,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> MealPlanResult:
    """One meal plan. In corpus mode `decision_client` screens the week's note; without one the note is dropped.

    The screen runs first, here, so nothing traced below it ever receives the raw note: the plan is made from
    the request without it and the screen's outcome.
    """
    if request.source == "corpus":
        return _generate_from_corpus(
            without_note(request),
            llm_router=llm_router,
            feedback=screen_feedback(request.human_feedback, decision_client=decision_client),
            corpus=corpus or RecipeCorpusStore(),
            rng=rng or _rng,
            now=now,
        )
    return _generate_from_saved(request, llm_router=llm_router)


@tracer.capture_method
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
        system=MEAL_PLAN_SYSTEM_PROMPT,
        user=json.dumps(context, default=str),
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


@tracer.capture_method
def _generate_from_corpus(
    request: MealPlanRequest,
    *,
    llm_router: LLMRouter,
    feedback: ScreenedFeedback,
    corpus: RecipeCorpusStore,
    rng: random.Random,
    now: datetime | None,
) -> MealPlanResult:
    """Corpus mode, as the agent graph's three nodes run it: prepare, choose, finalise.

    The sync route has no degraded path: an answer that keeps nothing stays an empty plan here, so this
    shape only ever gains fields. The agent's fallback is the graph's (§6.2), because it is the agent
    loop -- not the route -- that runs out of budget or steps.
    """
    prepared = pipeline.prepare(request, corpus=corpus, rng=rng, now=now, feedback=feedback)
    if not prepared.has_candidates:
        return MealPlanResult(
            suggestions=[], week_summary=pipeline.NO_MEALS_WEEK_SUMMARY, feedback_note=feedback.note_outcome
        )
    return pipeline.finalise(prepared, pipeline.choose(prepared, llm_router=llm_router))
