"""Thin adapters from a `NextAction` tool call to the framework-free tools in `meal_plan.tools`.

Each adapter builds the tool's input from the session (the request, the corpus, the prepared plan), runs the
tool, and returns two things: a compact JSON result the model reads on its next turn, and the prepared plan,
widened with any recipe the tool found so `finalise` may keep it. A call the tool refuses -- a filter that
would widen the session, an id that is not eligible -- comes back as an `error` the model can read and
correct; it never raises into the graph.

The progress line for each call is chosen here too, from the call alone, so it is written before the tool runs.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from glean.agent.actions import CreateCandidateMealPlans, GetEligibleRecipes, GetRecipes, ScoreMealPlan
from glean.meal_plan import balance, pipeline, tools
from glean.recipes.attributes import UNSURE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from glean.agent.actions import RecipeFilterArgs, ToolCall
    from glean.meal_plan.schemas import MealPlanRequest
    from glean.recipes.corpus import RecipeCorpusStore

# How many found recipes one result shows the model, and so how many it may go on to plan. The tool's own
# limit is 120; a prompt that carried 120 rows on every turn would cost more than the extra choice is worth.
SHOWN_RECIPES = 40
# A full recipe's method, as the model reads it: enough steps to judge the dish, not the whole page.
_SHOWN_METHOD_STEPS = 12
_SHOWN_STEP_CHARS = 240
# The words of a free-text search a progress line repeats back.
_PROGRESS_TEXT_CHARS = 40


@dataclass(frozen=True)
class ToolOutcome:
    """What one call gives the graph: the result the model reads, and the prepared plan after it."""

    result: dict[str, Any]
    prepared: pipeline.PreparedPlan


def progress_line(call: ToolCall) -> str:
    """The human line the session shows while this call runs (spec §6.2, "Progress lines")."""
    match call:
        case GetEligibleRecipes(filter=recipe_filter):
            text = " ".join((recipe_filter.text or "").split())[:_PROGRESS_TEXT_CHARS].strip()
            if text:
                return f"Looking for something {text}"
            if recipe_filter.uses_pantry:
                return "Finding dinners that use what you have"
            return "Checking what you cooked recently"
        case GetRecipes():
            return "Reading the recipes more closely"
        case ScoreMealPlan() | CreateCandidateMealPlans():
            return "Balancing proteins across the week"
    raise AssertionError(f"no progress line for {call!r}")


def run_tool(
    call: ToolCall,
    *,
    prepared: pipeline.PreparedPlan,
    request: MealPlanRequest,
    corpus: RecipeCorpusStore,
    now: datetime,
    session_id: str,
) -> ToolOutcome:
    """Run one tool call for this session. A refusal is an `error` result, not an exception."""
    seed = zlib.crc32(session_id.encode())
    match call:
        case GetEligibleRecipes(filter=recipe_filter):
            return _eligible(recipe_filter, prepared=prepared, request=request, corpus=corpus, now=now, seed=seed)
        case GetRecipes(ids=ids, detail=detail):
            ctx = pipeline.tool_context(request, corpus=corpus, now=now, seed=seed)
            return ToolOutcome(_details(tools.get_recipes(ids, detail, ctx)), prepared)
        case ScoreMealPlan(recipe_ids=recipe_ids):
            return ToolOutcome(_scored(recipe_ids, prepared), prepared)
        case CreateCandidateMealPlans(recipe_ids=recipe_ids):
            return ToolOutcome(_weeks(recipe_ids or prepared.offered_ids, prepared, seed=seed), prepared)
    raise AssertionError(f"no adapter for {call!r}")


def _eligible(
    recipe_filter: RecipeFilterArgs,
    *,
    prepared: pipeline.PreparedPlan,
    request: MealPlanRequest,
    corpus: RecipeCorpusStore,
    now: datetime,
    seed: int,
) -> ToolOutcome:
    try:
        narrowing = recipe_filter.recipe_filter()
        found = tools.get_eligible_recipes(narrowing, pipeline.tool_context(request, corpus=corpus, now=now, seed=seed))
    except ValueError as exc:  # FilterRejected, or a predicate its field does not take
        return ToolOutcome({"error": str(exc)}, prepared)
    shown = found.recipes[:SHOWN_RECIPES]
    return ToolOutcome(
        {
            "matched": found.matched,
            "floor_relaxed": found.floor_relaxed,
            "recipes": [_found_row(recipe) for recipe in shown],
        },
        pipeline.widen(prepared, shown, corpus=corpus),
    )


def _found_row(recipe: tools.EligibleRecipe) -> dict[str, Any]:
    """One found recipe as the model reads it: the candidate list's fields plus the attributes."""
    attributes = recipe.attributes
    return {
        "external_id": recipe.recipe_id,
        "title": recipe.title,
        "cuisine": recipe.cuisine,
        "active_time_mins": attributes.active_time_mins(recipe.total_time_mins),
        "main_protein": _known(attributes.main_protein.value),
        "main_carb": _known(attributes.main_carb.value),
        "dish_type": _known(attributes.dish_type.value),
        "pantry_items": list(recipe.pantry_items),
        "urgent_pantry_items": [item.name for item in recipe.urgent_items],
        "cooked_days_ago": None if recipe.days_since_cooked is None else round(recipe.days_since_cooked),
    }


def _details(details: tools.RecipeDetails) -> dict[str, Any]:
    return {
        "recipes": [
            {
                "external_id": card.recipe_id,
                "title": card.title,
                "cuisine": card.cuisine,
                "total_time_mins": card.total_time_mins,
                "active_time_mins": card.active_time_mins,
                "attributes": {name: value for name, value in card.attributes.as_mapping().items() if value != UNSURE},
                "key_ingredients": list(card.key_ingredients),
                **({"ingredients": list(card.ingredients)} if card.ingredients else {}),
                **(
                    {"method": [step[:_SHOWN_STEP_CHARS] for step in card.method[:_SHOWN_METHOD_STEPS]]}
                    if card.method
                    else {}
                ),
            }
            for card in details.recipes
        ],
        "unknown": list(details.unknown),
    }


def _scored(recipe_ids: Sequence[str], prepared: pipeline.PreparedPlan) -> dict[str, Any]:
    """The week's score and breakdown, or why it cannot be scored: an id the plan may not use, or a repeat."""
    try:
        score = tools.score_meal_plan(recipe_ids, balance.scoring_context(prepared.facts))
    except tools.UnknownRecipeIds as exc:
        return {"error": f"these ids are not recipes you may plan: {exc.args[0]}"}
    except tools.DuplicateRecipeIds as exc:
        return {"error": str(exc)}
    return {"week": _week(balance.CandidateWeek.from_score(score)), "best_candidate_week_score": _best(prepared)}


def _weeks(recipe_ids: Sequence[str], prepared: pipeline.PreparedPlan, *, seed: int) -> dict[str, Any]:
    try:
        weeks = balance.scored_weeks(
            balance.scoring_context(prepared.facts), recipe_ids, prepared.meals_per_week, seed=seed
        )
    except tools.UnknownRecipeIds as exc:
        return {"error": f"these ids are not recipes you may plan: {exc.args[0]}"}
    return {"weeks": [_week(week) for week in weeks]}


def _week(week: balance.CandidateWeek) -> dict[str, Any]:
    """A scored week as prompt text: rounded, because the model compares, it does not do arithmetic."""
    return {
        "recipe_ids": week.recipe_ids,
        "score": round(week.total, 2),
        "terms": {term: round(points, 2) for term, points in week.terms.items()},
        "penalties": [
            f"{penalty.term} {penalty.points:+g}" + (f" ({penalty.detail})" if penalty.detail else "")
            for penalty in week.penalties
        ],
    }


def _best(prepared: pipeline.PreparedPlan) -> float | None:
    return round(prepared.weeks[0].total, 2) if prepared.weeks else None


def _known(value: str) -> str | None:
    return None if value == UNSURE else value
