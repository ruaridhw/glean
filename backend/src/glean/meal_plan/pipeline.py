"""The corpus meal plan as three steps: prepare, choose, finalise.

`POST /meal-plan` runs them one after another, and the agent graph (V1) runs the same three
functions as its three nodes, so a session and the synchronous endpoint return the same picks
and the same reason text for the same request and seed. Nothing here knows about sessions,
queues or LangGraph: the steps take plain values, and the LLM call goes through `LLMRouter`.

- **prepare** is deterministic. It samples the candidate recipes the model will see, files every
  urgent pantry item under the candidates that use it, and writes the model's one user message.
  Dietary flags, the time cap, meals already planned and the six-week recency floor are applied
  here (V2 and V4), so the offered set is the dietary guarantee.
- **choose** is the only LLM step. It asks the model to pick from the candidates.
- **finalise** rejects anything the model was not offered (ids, already-planned meals, over-long
  lists) and writes each meal's reason: the model's prose without any sentence that dates
  something, then one sentence the server wrote, plus `uses_up`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.llm import Feature
from glean.meal_plan.candidates import PantryItem, sample_corpus_candidates, urgent_pantry_uses
from glean.meal_plan.eligibility import CookedMeal
from glean.meal_plan.schemas import (
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanRequest,
    MealPlanResult,
    MealPlanSuggestion,
    UsedUpPantryItem,
)
from glean.observability import logger

if TYPE_CHECKING:
    import random
    from collections.abc import Sequence

    from glean.llm import LLMRouter
    from glean.recipes.corpus import RecipeCorpusStore

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
# Sentence ends: the punctuation with any closing quotes or brackets that belong to it, then the space
# that follows. Group 1 is the end of the sentence itself, so its punctuation is never sliced off.
_SENTENCE_BOUNDARY_RE = re.compile(r"([.!?][\"')\]]*)(\s+)")
# A period after one of these never ends a sentence ("e.g. coriander").
_INLINE_ABBREVIATIONS = frozenset({"e.g", "i.e", "approx", "etc", "vs", "fig", "no", "dr", "mr", "mrs", "ms", "st"})
# Units that read as abbreviations mid-sentence ("1.5 tbsp. of oil") but end a real sentence when the
# next word starts a new one ("Ready in 20 min. Serves 2").
_MEASURE_ABBREVIATIONS = frozenset({"tbsp", "tsp", "oz", "lb", "lbs", "kg", "ml", "min", "mins", "hr", "hrs"})
_WEEKDAY = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_DAY_NUMBER = r"\d{1,2}(?:st|nd|rd|th)?"
_DATE_CONTEXT = rf"(?:{_WEEKDAY}|{_MONTH}|{_DAY_NUMBER}|tomorrow|today|tonight|the|next|end)\b"
# Saying when something goes off is the app's job, not the model's. Word boundaries keep "mango
# offcuts" and "drop it off" out, and the date-shaped phrases only claim an expiry when a date follows
# ("use by hand" is a method, "use by Friday" is a claim).
_EXPIRY_CLAIM_RES = (
    re.compile(r"\bexpir(?:y|ies|es|ed|ing|ation)\b", re.IGNORECASE),
    re.compile(r"\b(?:go|goes|going|went|gone)\s+off\b", re.IGNORECASE),
    re.compile(r"\bgood\s+until\b", re.IGNORECASE),
    re.compile(rf"\b(?:use[-\s]by|sell[-\s]by|best[-\s]before)\s+(?:on\s+|by\s+)?{_DATE_CONTEXT}", re.IGNORECASE),
)


class UrgentUse(BaseModel):
    """One urgent pantry item a candidate uses, as `finalise` needs it to write the expiry sentence."""

    name: str
    expires_in_days: int | None = None


class PreparedPlan(BaseModel):
    """What `prepare` hands `choose`: the model's message, and what `finalise` validates against.

    Every field is JSON, so the agent graph can checkpoint it and a resumed run finds the same
    candidates and the same reference date.
    """

    user: str = Field(description="The model's one user message: the candidates and the household's constraints.")
    reference_date: date = Field(description="The household's calendar date, which any going-off day is measured from.")
    meals_per_week: int
    offered_ids: list[str] = Field(description="Every external_id the model was offered. Nothing else may be planned.")
    excluded_ids: list[str] = Field(description="Recipes already in the plan; generation only ever tops up.")
    urgent_uses: dict[str, list[UrgentUse]] = Field(
        description="Per offered external_id, the urgent pantry items that recipe uses, soonest to go off first."
    )

    @property
    def has_candidates(self) -> bool:
        return bool(self.offered_ids)


def prepare(
    request: MealPlanRequest,
    *,
    corpus: RecipeCorpusStore,
    rng: random.Random,
    now: datetime | None = None,
) -> PreparedPlan:
    """Sample the candidates the model may pick from, and write its message. No LLM call."""
    request_now = now or datetime.now(UTC)
    # The phone measured `expires_in_days` from its own local date; without it, fall back to the server's.
    reference_date = request.local_date or request_now.date()
    pantry = [
        PantryItem(name=item.name, urgency_score=item.urgency_score, expires_in_days=item.expires_in_days)
        for item in request.pantry
    ]
    # `cooked_history`'s ratings decide what may be offered (a thumbs-down recipe never is), and nothing
    # else here reads them. Its notes go no further than this function's argument: the only path a note
    # will take into a prompt is the screened human-feedback channel, which is not built yet. Until that
    # screen exists the note is stored on the phone and validated on the wire, and that is all.
    candidates = sample_corpus_candidates(
        corpus,
        pantry=pantry,
        dietary_flags=request.dietary_flags,
        max_total_time_mins=request.max_active_time_mins,
        exclude_external_ids=request.exclude_external_ids,
        rng=rng,
        cooked=[
            CookedMeal(
                recipe_id=meal.recipe_id,
                title=meal.title,
                cooked_at=meal.cooked_at,
                rating=meal.rating,
            )
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
    return PreparedPlan(
        user=json.dumps(context, default=str),
        reference_date=reference_date,
        meals_per_week=request.meals_per_week,
        offered_ids=[candidate.external_id for candidate in candidates],
        excluded_ids=list(request.exclude_external_ids),
        urgent_uses={
            candidate.external_id: [
                UrgentUse(name=item.name, expires_in_days=item.expires_in_days)
                for item in urgent_uses.get(candidate.external_id, ())
            ]
            for candidate in candidates
        },
    )


def choose(
    prepared: PreparedPlan, *, llm_router: LLMRouter, timeout_ms: int | None = None
) -> list[CorpusMealPlanRecipe]:
    """Ask the model to pick from the candidates. Its answer is unvalidated; `finalise` judges it.

    *timeout_ms* bounds the call. The agent passes what is left of its 90 s budget, so one slow model
    cannot hold the run past the point where the worker can still write an outcome.
    """
    response = llm_router.invoke(
        Feature.MEAL_PLAN_GENERATION,
        CorpusMealPlanResponse,
        system=CORPUS_MEAL_PLAN_SYSTEM_PROMPT,
        user=prepared.user,
        timeout_ms=timeout_ms,
    )
    return response.suggestions


def finalise(prepared: PreparedPlan, picks: Sequence[CorpusMealPlanRecipe]) -> MealPlanResult:
    """Keep only choices that are valid, and write each meal's reason and `uses_up`.

    Valid means: offered to the model (so the dietary decisions, the time cap and the recency floor
    held), not already in the plan (generation only tops up, ADR 0020), and no more than one per slot.
    """
    offered = set(prepared.offered_ids)
    excluded = set(prepared.excluded_ids)
    invented = [pick.external_id for pick in picks if pick.external_id not in offered]
    if invented:
        logger.error("corpus meal plan chose recipes that were not offered; dropping", extra={"external_ids": invented})
    planned = [pick.external_id for pick in picks if pick.external_id in excluded]
    if planned:
        logger.error("corpus meal plan chose recipes already in the plan; dropping", extra={"external_ids": planned})
    kept = [pick for pick in picks if pick.external_id in offered and pick.external_id not in excluded]
    if len(kept) > prepared.meals_per_week:
        logger.error(
            "corpus meal plan exceeded meals_per_week; truncating",
            extra={"returned": len(kept), "limit": prepared.meals_per_week},
        )
    chosen = _reconciled(kept[: prepared.meals_per_week], prepared)
    logger.info("meal plan generated", extra={"count": len(chosen)})
    return MealPlanResult(suggestions=chosen)


def _urgent_item_payload(item: PantryItem, *, reference_date: date) -> dict[str, object]:
    """What the model needs to say when an item goes off: its name and the day, not just a day count."""
    return {
        "name": item.name,
        "expires_in_days": item.expires_in_days,
        "goes_off": _goes_off_day(item, reference_date=reference_date),
    }


def _reconciled(chosen: Sequence[CorpusMealPlanRecipe], prepared: PreparedPlan) -> list[MealPlanSuggestion]:
    """Each chosen meal as a proposal: a reason with one canonical expiry sentence, plus `uses_up`.

    The prompt tells the model not to date anything, but a model that dates anyway would put a wrong or
    contradictory day in front of the household. Rather than edit inside its prose, any whole sentence
    that claims an expiry is dropped and one sentence the server wrote is appended -- so the reason
    always carries exactly one expiry statement, naming up to `_MAX_NAMED_URGENT_ITEMS` of them, while
    `uses_up` carries every urgent item the recipe uses.
    """
    suggestions: list[MealPlanSuggestion] = []
    for suggestion in chosen:
        items = sorted(
            prepared.urgent_uses.get(suggestion.external_id, ()),
            key=lambda urgent_item: (urgent_item.expires_in_days or 0, urgent_item.name.casefold()),
        )
        reason = suggestion.reason
        if items:
            reason = _canonical_reason(reason, items, reference_date=prepared.reference_date)
        suggestions.append(
            MealPlanSuggestion(
                external_id=suggestion.external_id,
                title=suggestion.title,
                reason=reason,
                uses_up=[_used_up(item, reference_date=prepared.reference_date) for item in items],
            )
        )
    return suggestions


def _canonical_reason(reason: str, items: Sequence[UrgentUse], *, reference_date: date) -> str:
    """The model's reason without any sentence that dates something, then the canonical sentence."""
    kept = [sentence for sentence in _sentences(reason) if not _claims_expiry(sentence)]
    canonical = _canonical_sentence(items, reference_date=reference_date)
    text = " ".join(kept)
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return f"{text} {canonical}".strip() if text else canonical


def _sentences(reason: str) -> list[str]:
    """The reason's sentences, keeping abbreviations such as "e.g." inside the one they belong to."""
    sentences: list[str] = []
    start = 0
    for boundary in _SENTENCE_BOUNDARY_RE.finditer(reason):
        if _continues_sentence(reason, boundary):
            continue
        sentence = reason[start : boundary.end(1)].strip()
        if sentence:
            sentences.append(sentence)
        start = boundary.end()
    tail = reason[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _continues_sentence(reason: str, boundary: re.Match[str]) -> bool:
    """Whether this period closes an abbreviation and the sentence carries on after it."""
    before = reason[: boundary.start()]
    token = before.split()[-1].casefold() if before.strip() else ""
    if token in _INLINE_ABBREVIATIONS or len(token) == 1:
        return True
    following = reason[boundary.end() :]
    if token not in _MEASURE_ABBREVIATIONS or not following:
        return False
    return following[0].islower() or following[0].isdigit()


def _claims_expiry(sentence: str) -> bool:
    return any(pattern.search(sentence) for pattern in _EXPIRY_CLAIM_RES)


def _canonical_sentence(items: Sequence[UrgentUse], *, reference_date: date) -> str:
    named = [
        f"{item.name} ({_goes_off_phrase(item, reference_date=reference_date)})"
        for item in items[:_MAX_NAMED_URGENT_ITEMS]
    ]
    body = named[0] if len(named) == 1 else f"{', '.join(named[:-1])} and {named[-1]}"
    return f"Uses up your {body}."


def _used_up(item: UrgentUse, *, reference_date: date) -> UsedUpPantryItem:
    return UsedUpPantryItem(
        name=item.name,
        expires_in_days=item.expires_in_days,
        goes_off=_goes_off_day(item, reference_date=reference_date),
    )


def _goes_off_day(item: UrgentUse | PantryItem, *, reference_date: date) -> str:
    return (reference_date + timedelta(days=item.expires_in_days or 0)).strftime("%a")


def _goes_off_phrase(item: UrgentUse, *, reference_date: date) -> str:
    when = "went off" if item.expires_in_days is not None and item.expires_in_days < 0 else "goes off"
    return f"{when} {_goes_off_day(item, reference_date=reference_date)}"
