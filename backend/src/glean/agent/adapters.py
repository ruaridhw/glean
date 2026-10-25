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

from glean.agent.actions import MAX_FULL_IDS, CreateCandidateMealPlans, GetEligibleRecipes, GetRecipes, ScoreMealPlan
from glean.meal_plan import balance, pipeline, tools
from glean.recipes.attributes import UNSURE, Cuisine, normalise_cuisine

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from glean.agent.actions import RecipeFilterArgs, ToolCall
    from glean.meal_plan.schemas import MealPlanRequest
    from glean.recipes.corpus import RecipeCorpusStore

# How many found recipes one result shows the model, and so how many it may go on to plan. The tool's own
# limit is 120; a prompt that carried 120 rows on every turn would cost more than the extra choice is worth.
SHOWN_RECIPES = 40
# Recipe text is third-party (anyone signed in can import a recipe), so every piece of it is clipped before it
# reaches a prompt or the checkpoint: a title, a cuisine, a name, and a full recipe's lines and steps. Enough to
# judge a dish, never the whole page; with `MAX_FULL_IDS` a full read stays near 40 KB however long the page.
_TITLE_CHARS = 120
_LABEL_CHARS = 40
_NAME_CHARS = 60
_SHOWN_KEY_INGREDIENTS = 12
_SHOWN_INGREDIENT_LINES = 20
_LINE_CHARS = 100
_SHOWN_METHOD_STEPS = 8
_SHOWN_STEP_CHARS = 200
_ERROR_CHARS = 300
# How many words of a search a progress line looks through for a cuisine it may name.
_PROGRESS_SEARCH_WORDS = 8


@dataclass(frozen=True)
class ToolOutcome:
    """What one call gives the graph: the result the model reads, and the prepared plan after it."""

    result: dict[str, Any]
    prepared: pipeline.PreparedPlan


def progress_line(call: ToolCall) -> str:
    """The human line the session shows while this call runs (spec §6.2, "Progress lines")."""
    match call:
        case GetEligibleRecipes(filter=recipe_filter):
            if recipe_filter.text and recipe_filter.text.strip():
                cuisine = _cuisine_named(recipe_filter.text)
                return f"Looking for something {cuisine}" if cuisine else "Looking for something different"
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
    context: tools.EligibilityContext | None = None,
) -> ToolOutcome:
    """Run one tool call for this session. A refusal is an `error` result, not an exception.

    *context* is the corpus as the corpus tools read it (`tool_context`, which reads every summary, answer and
    decision), built once per run and passed back in by the caller; without it, it is built for this call.
    """
    seed = session_seed(session_id)
    match call:
        case GetEligibleRecipes(filter=recipe_filter):
            ctx = context or pipeline.tool_context(request, corpus=corpus, now=now, seed=seed)
            return _eligible(recipe_filter, prepared=prepared, ctx=ctx, corpus=corpus)
        case GetRecipes(ids=ids, detail=detail):
            if detail == "full" and len(ids) > MAX_FULL_IDS:
                return ToolOutcome({"error": f"ask for at most {MAX_FULL_IDS} recipes in full at a time"}, prepared)
            ctx = context or pipeline.tool_context(request, corpus=corpus, now=now, seed=seed)
            return ToolOutcome(_details(tools.get_recipes(ids, detail, ctx)), prepared)
        case ScoreMealPlan(recipe_ids=recipe_ids):
            return ToolOutcome(_scored(recipe_ids, prepared), prepared)
        case CreateCandidateMealPlans(recipe_ids=recipe_ids):
            return ToolOutcome(_weeks(recipe_ids or prepared.offered_ids, prepared, seed=seed), prepared)
    raise AssertionError(f"no adapter for {call!r}")


def session_seed(session_id: str) -> int:
    """The tools' tie-break seed for one session: stable, so a resumed run ranks exactly as the first did."""
    return zlib.crc32(session_id.encode())


def _eligible(
    recipe_filter: RecipeFilterArgs,
    *,
    prepared: pipeline.PreparedPlan,
    ctx: tools.EligibilityContext,
    corpus: RecipeCorpusStore,
) -> ToolOutcome:
    try:
        narrowing = recipe_filter.recipe_filter()
        found = tools.get_eligible_recipes(narrowing, ctx)
    except ValueError as exc:  # FilterRejected, or a predicate its field does not take
        return ToolOutcome({"error": clip(str(exc), _ERROR_CHARS)}, prepared)
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
        "title": clip(recipe.title, _TITLE_CHARS),
        "cuisine": clip(recipe.cuisine, _LABEL_CHARS),
        "active_time_mins": attributes.active_time_mins(recipe.total_time_mins),
        "main_protein": _known(attributes.main_protein.value),
        "main_carb": _known(attributes.main_carb.value),
        "dish_type": _known(attributes.dish_type.value),
        "pantry_items": [clip(name, _NAME_CHARS) for name in recipe.pantry_items],
        "urgent_pantry_items": [clip(item.name, _NAME_CHARS) for item in recipe.urgent_items],
        "cooked_days_ago": None if recipe.days_since_cooked is None else round(recipe.days_since_cooked),
    }


def _details(details: tools.RecipeDetails) -> dict[str, Any]:
    """The cards as the model reads them, every piece of recipe text clipped. A full card's lines replace its key
    ingredients, which they repeat."""
    return {
        "recipes": [
            {
                "external_id": card.recipe_id,
                "title": clip(card.title, _TITLE_CHARS),
                "cuisine": clip(card.cuisine, _LABEL_CHARS),
                "total_time_mins": card.total_time_mins,
                "active_time_mins": card.active_time_mins,
                "attributes": {name: value for name, value in card.attributes.as_mapping().items() if value != UNSURE},
                **(
                    {
                        "ingredients": [clip(line, _LINE_CHARS) for line in card.ingredients[:_SHOWN_INGREDIENT_LINES]],
                        "method": [clip(step, _SHOWN_STEP_CHARS) for step in card.method[:_SHOWN_METHOD_STEPS]],
                    }
                    if card.ingredients or card.method
                    else {
                        "key_ingredients": [
                            clip(name, _NAME_CHARS) for name in card.key_ingredients[:_SHOWN_KEY_INGREDIENTS]
                        ]
                    }
                ),
            }
            for card in details.recipes
        ],
        "unknown": list(details.unknown),
    }


def _scored(recipe_ids: Sequence[str], prepared: pipeline.PreparedPlan) -> dict[str, Any]:
    """The week's score and breakdown, or why it cannot be scored: an id the plan may not use, or a repeat."""
    try:
        score = tools.score_meal_plan(recipe_ids, pipeline.scoring_context_of(prepared))
    except tools.UnknownRecipeIds as exc:
        return {"error": clip(f"these ids are not recipes you may plan: {exc.args[0]}", _ERROR_CHARS)}
    except tools.DuplicateRecipeIds as exc:
        return {"error": clip(str(exc), _ERROR_CHARS)}
    return {"week": _week(balance.CandidateWeek.from_score(score)), "best_candidate_week_score": _best(prepared)}


def _weeks(recipe_ids: Sequence[str], prepared: pipeline.PreparedPlan, *, seed: int) -> dict[str, Any]:
    try:
        weeks = balance.scored_weeks(
            pipeline.scoring_context_of(prepared), recipe_ids, prepared.meals_per_week, seed=seed
        )
    except tools.UnknownRecipeIds as exc:
        return {"error": clip(f"these ids are not recipes you may plan: {exc.args[0]}", _ERROR_CHARS)}
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


def _cuisine_named(text: str) -> str | None:
    """The cuisine a search names, as our own label ("Korean"), or None when it names none we know.

    A progress line is shown to the household, and the search text is the model's, which recipe text it has read
    can steer. So the line never repeats that text: it says only a cuisine from the G1 list, in our spelling.
    """
    words = text.casefold().split()[:_PROGRESS_SEARCH_WORDS]
    for size in (2, 1):
        for start in range(len(words) - size + 1):
            cuisine = normalise_cuisine(" ".join(words[start : start + size]))
            if cuisine is not None and cuisine is not Cuisine.OTHER:
                return cuisine.value.replace("_", " ").title()
    return None


def _known(value: str) -> str | None:
    return None if value == UNSURE else value


def clip(text: str | None, chars: int) -> str | None:
    """*text* cut to *chars* characters, marked when it was cut; None stays None."""
    if text is None or len(text) <= chars:
        return text
    return f"{text[: chars - 1]}…"
