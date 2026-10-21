from __future__ import annotations

import json
import random
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from glean.llm import Feature
from glean.meal_plan.candidates import PantryItem, mentions_item, sample_corpus_candidates, urgent_pantry_uses
from glean.meal_plan.eligibility import CookedMeal
from glean.meal_plan.schemas import (
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanRequest,
    MealPlanResponse,
    MealPlanResult,
    MealPlanSuggestion,
)
from glean.observability import logger, tracer
from glean.recipes.corpus import RecipeCorpusStore

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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
- When a candidate lists urgent_pantry_items, say in its reason that the meal uses one up, naming the
  item and when it goes off, using the goes_off day given, e.g. "uses up your coriander (goes off Thu)".
  Those items go off within days, so they need cooking this week.
- Respect dietary_flags by checking each candidate's ingredients; skip any candidate that conflicts
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Vary cuisines and main ingredients across the week
- Prefer candidates whose cooked_days_ago is null. A non-null value means the household cooked that recipe
  that many days ago and it is offered only because too few fresh candidates remained; choose one of the
  others whenever one fits.
- Return AT MOST meals_per_week planned meals — never exceed meals_per_week. Returning fewer is
  fine; do not pad the list with weaker choices to reach the limit."""

_MAX_CANDIDATE_INGREDIENTS = 12
_WEEKDAY_WORD = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"
# A model-written expiry claim, with the punctuation that usually hugs it.
_EXPIRY_CLAIM_RE = re.compile(
    rf"\s*(?:[,;(]\s*)?(?:which\s+|and\s+|it\s+)?(?:goes|went)\s+off\s+(?:on\s+)?(?P<day>{_WEEKDAY_WORD})\s*[).]?",
    re.IGNORECASE,
)
_rng = random.Random()  # noqa: S311 - varies recipe sampling; not security-sensitive


@tracer.capture_method
def generate_meal_plan(
    request: MealPlanRequest,
    *,
    llm_router: LLMRouter,
    corpus: RecipeCorpusStore | None = None,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> MealPlanResult:
    if request.source == "corpus":
        return _generate_from_corpus(
            request, llm_router=llm_router, corpus=corpus or RecipeCorpusStore(), rng=rng or _rng, now=now
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


def _generate_from_corpus(
    request: MealPlanRequest,
    *,
    llm_router: LLMRouter,
    corpus: RecipeCorpusStore,
    rng: random.Random,
    now: datetime | None,
) -> MealPlanResult:
    request_now = now or datetime.now(UTC)
    # The phone measured `expires_in_days` from its own local date; without it, fall back to the server's.
    reference_date = request.local_date or request_now.date()
    pantry = [
        PantryItem(
            name=item.name,
            urgency_score=item.urgency_score,
            expires_in_days=item.expires_in_days,
        )
        for item in request.pantry
    ]
    candidates = sample_corpus_candidates(
        corpus,
        pantry=pantry,
        dietary_flags=request.dietary_flags,
        max_total_time_mins=request.max_active_time_mins,
        exclude_external_ids=request.exclude_external_ids,
        rng=rng,
        cooked=[
            CookedMeal(recipe_id=meal.recipe_id, title=meal.title, cooked_at=meal.cooked_at)
            for meal in request.cooked_history
        ],
        slots=request.meals_per_week,
        now=request_now,
    )
    urgent_uses = urgent_pantry_uses(corpus, pantry, [candidate.external_id for candidate in candidates])
    logger.info(
        "generating corpus meal plan",
        extra={
            "pantry_items": len(request.pantry),
            "candidates": len(candidates),
            "urgent_pantry_items": len({item.name for items in urgent_uses.values() for item in items}),
        },
    )
    if not candidates:
        return MealPlanResult(suggestions=[])

    context = {
        "pantry": [item.model_dump() for item in request.pantry],
        "candidates": [
            {
                "external_id": candidate.external_id,
                "title": candidate.title,
                "cuisine": candidate.summary.cuisine,
                "total_time_mins": candidate.summary.total_time_mins,
                "ingredients": candidate.summary.ingredient_names[:_MAX_CANDIDATE_INGREDIENTS],
                # Null for a recipe the household has not cooked recently; a number marks a fallback.
                "cooked_days_ago": None if candidate.cooked_days_ago is None else round(candidate.cooked_days_ago),
                "urgent_pantry_items": [
                    _urgent_item_payload(item, reference_date=reference_date)
                    for item in urgent_uses.get(candidate.external_id, ())
                ],
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
        system=CORPUS_MEAL_PLAN_SYSTEM_PROMPT,
        user=json.dumps(context, default=str),
    )

    offered = {candidate.external_id for candidate in candidates}
    chosen = [suggestion for suggestion in response.suggestions if suggestion.external_id in offered]
    if len(chosen) < len(response.suggestions):
        logger.error(
            "corpus meal plan chose recipes that were not offered; dropping",
            extra={"external_ids": [s.external_id for s in response.suggestions if s.external_id not in offered]},
        )
    chosen = _name_urgent_items(chosen[: request.meals_per_week], urgent_uses, reference_date=reference_date)

    logger.info("meal plan generated", extra={"count": len(chosen)})
    return MealPlanResult(suggestions=[MealPlanSuggestion(**suggestion.model_dump()) for suggestion in chosen])


def _urgent_item_payload(item: PantryItem, *, reference_date: date) -> dict[str, object]:
    """What the model needs to say when an item goes off: its name and the day, not just a day count."""
    return {
        "name": item.name,
        "expires_in_days": item.expires_in_days,
        "goes_off": _goes_off_day(item, reference_date=reference_date),
    }


def _name_urgent_items(
    chosen: Sequence[CorpusMealPlanRecipe],
    urgent_uses: Mapping[str, Sequence[PantryItem]],
    *,
    reference_date: date,
) -> list[CorpusMealPlanRecipe]:
    """Make each reason that uses an urgent item name it and when it goes off.

    The prompt asks the model for this, but a reason that quietly omits it would hide the one thing the
    household most needs to know. One urgent item per reason is enough, and a reason is only left alone
    when it names that item in full *and* states the right day; anything less gets the missing part
    appended, without naming the item a second time.
    """
    named: list[CorpusMealPlanRecipe] = []
    for suggestion in chosen:
        items = urgent_uses.get(suggestion.external_id, ())
        if not any(_states_when_it_goes_off(suggestion.reason, item, reference_date=reference_date) for item in items):
            reason = suggestion.reason.rstrip()
            if items:
                # The soonest to go off is the one worth naming if the model named none of them.
                item = min(items, key=lambda urgent_item: urgent_item.expires_in_days or 0)
                reason = _repaired_reason(reason, item, reference_date=reference_date)
            suggestion = suggestion.model_copy(update={"reason": reason})
        named.append(suggestion)
    return named


def _states_when_it_goes_off(reason: str, item: PantryItem, *, reference_date: date) -> bool:
    """Whether the reason names the whole item and claims the day it actually goes off.

    A weekday elsewhere in the prose is not a claim about this item: "For Thu dinner, uses coriander
    (goes off Fri)" says nothing true about the coriander.
    """
    return mentions_item(reason, item.name) and _day_claimed(reason, item, reference_date=reference_date)


def _day_claimed(reason: str, item: PantryItem, *, reference_date: date) -> bool:
    day = reference_date + timedelta(days=item.expires_in_days or 0)
    claimed = {match.group("day").casefold() for match in _EXPIRY_CLAIM_RE.finditer(reason)}
    return day.strftime("%a").casefold() in claimed or day.strftime("%A").casefold() in claimed


def _repaired_reason(reason: str, item: PantryItem, *, reference_date: date) -> str:
    """The reason with one correct expiry clause at the end: the model's own day claims are dropped.

    Leaving a model-written day in place would put two contradictory dates in front of the household, so
    the claim is removed rather than contradicted. Other prose (a weekday that describes the dinner, say)
    is left alone.
    """
    without_claims = _strip_expiry_claims(reason)
    phrase = _goes_off_phrase(item, reference_date=reference_date)
    names_item = mentions_item(without_claims, item.name)
    clause = f"It {phrase}." if names_item else f"Uses up your {item.name} ({phrase})."
    return " ".join(part for part in (without_claims, clause) if part)


def _strip_expiry_claims(reason: str) -> str:
    """The reason without any "goes off <day>" claim, tidied into a sentence."""
    stripped = re.sub(r"\s+([.,;])", r"\1", _EXPIRY_CLAIM_RE.sub("", reason))
    stripped = re.sub(r"[,;(]\s*$", "", stripped)
    stripped = re.sub(r"\s?,\s*$", "", stripped)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    if stripped and stripped[-1] not in ".!?":
        stripped = f"{stripped}."
    return stripped


def _goes_off_day(item: PantryItem, *, reference_date: date) -> str:
    return (reference_date + timedelta(days=item.expires_in_days or 0)).strftime("%a")


def _goes_off_phrase(item: PantryItem, *, reference_date: date) -> str:
    when = "went off" if item.expires_in_days is not None and item.expires_in_days < 0 else "goes off"
    return f"{when} {_goes_off_day(item, reference_date=reference_date)}"
