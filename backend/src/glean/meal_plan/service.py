from __future__ import annotations

import json
import random
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from glean.llm import Feature
from glean.meal_plan.candidates import PantryItem, sample_corpus_candidates, urgent_pantry_uses
from glean.meal_plan.eligibility import CookedMeal
from glean.meal_plan.schemas import (
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanRequest,
    MealPlanResponse,
    MealPlanResult,
    MealPlanSuggestion,
    UsedUpPantryItem,
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
- When a candidate lists urgent_pantry_items, you may say the meal uses one up, naming the item (for
  example "uses the coriander"). Never state an expiry day, a weekday, or a "goes off" timing: the app
  adds the date itself, so any day you write will be wrong.
- Respect dietary_flags by checking each candidate's ingredients; skip any candidate that conflicts
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Vary cuisines and main ingredients across the week
- Prefer candidates whose cooked_days_ago is null. A non-null value means the household cooked that recipe
  that many days ago and it is offered only because too few fresh candidates remained; choose one of the
  others whenever one fits.
- Return AT MOST meals_per_week planned meals — never exceed meals_per_week. Returning fewer is
  fine; do not pad the list with weaker choices to reach the limit."""

_MAX_CANDIDATE_INGREDIENTS = 12
# How many urgent items one canonical sentence names; the rest still reach the app in `uses_up`.
_MAX_NAMED_URGENT_ITEMS = 3
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# Any sentence saying when something goes off is the app's job, not the model's.
_EXPIRY_PHRASES = ("goes off", "go off", "went off", "gone off", "expires", "expire", "use by", "use-by", "best before")
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
    chosen = _reconciled(chosen[: request.meals_per_week], urgent_uses, reference_date=reference_date)

    logger.info("meal plan generated", extra={"count": len(chosen)})
    return MealPlanResult(suggestions=chosen)


def _urgent_item_payload(item: PantryItem, *, reference_date: date) -> dict[str, object]:
    """What the model needs to say when an item goes off: its name and the day, not just a day count."""
    return {
        "name": item.name,
        "expires_in_days": item.expires_in_days,
        "goes_off": _goes_off_day(item, reference_date=reference_date),
    }


def _reconciled(
    chosen: Sequence[CorpusMealPlanRecipe],
    urgent_uses: Mapping[str, Sequence[PantryItem]],
    *,
    reference_date: date,
) -> list[MealPlanSuggestion]:
    """Each chosen meal as a proposal: a reason with one canonical expiry sentence, plus `uses_up`.

    The prompt tells the model not to date anything, but a model that dates anyway would put a wrong or
    contradictory day in front of the household. Rather than edit inside its prose, any whole sentence
    that claims an expiry is dropped and one sentence the server wrote is appended -- so the reason
    always carries exactly one expiry statement, naming every urgent item the recipe uses.
    """
    suggestions: list[MealPlanSuggestion] = []
    for suggestion in chosen:
        items = sorted(
            urgent_uses.get(suggestion.external_id, ()),
            key=lambda urgent_item: (urgent_item.expires_in_days or 0, urgent_item.name.casefold()),
        )
        reason = suggestion.reason
        if items:
            reason = _canonical_reason(reason, items, reference_date=reference_date)
        suggestions.append(
            MealPlanSuggestion(
                external_id=suggestion.external_id,
                title=suggestion.title,
                reason=reason,
                uses_up=[_used_up(item, reference_date=reference_date) for item in items],
            )
        )
    return suggestions


def _canonical_reason(reason: str, items: Sequence[PantryItem], *, reference_date: date) -> str:
    """The model's reason without any sentence that dates something, then the canonical sentence."""
    kept = [sentence for sentence in _sentences(reason) if not _claims_expiry(sentence)]
    canonical = _canonical_sentence(items, reference_date=reference_date)
    return " ".join([*kept, canonical])


def _sentences(reason: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(reason.strip()) if sentence.strip()]


def _claims_expiry(sentence: str) -> bool:
    words = sentence.casefold()
    return any(phrase in words for phrase in _EXPIRY_PHRASES)


def _canonical_sentence(items: Sequence[PantryItem], *, reference_date: date) -> str:
    named = [
        f"{item.name} ({_goes_off_phrase(item, reference_date=reference_date)})"
        for item in items[:_MAX_NAMED_URGENT_ITEMS]
    ]
    body = named[0] if len(named) == 1 else f"{', '.join(named[:-1])} and {named[-1]}"
    return f"Uses up your {body}."


def _used_up(item: PantryItem, *, reference_date: date) -> UsedUpPantryItem:
    return UsedUpPantryItem(
        name=item.name,
        expires_in_days=item.expires_in_days,
        goes_off=_goes_off_day(item, reference_date=reference_date),
    )


def _goes_off_day(item: PantryItem, *, reference_date: date) -> str:
    return (reference_date + timedelta(days=item.expires_in_days or 0)).strftime("%a")


def _goes_off_phrase(item: PantryItem, *, reference_date: date) -> str:
    when = "went off" if item.expires_in_days is not None and item.expires_in_days < 0 else "goes off"
    return f"{when} {_goes_off_day(item, reference_date=reference_date)}"
