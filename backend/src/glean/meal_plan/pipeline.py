"""The corpus meal plan as three steps: prepare, choose, finalise.

`POST /meal-plan` runs them one after another, and the agent graph (V1) runs the same three
functions as its three nodes, so a session and the synchronous endpoint return the same picks
and the same reason text for the same request and seed. Nothing here knows about sessions,
queues or LangGraph: the steps take plain values, and the LLM call goes through `LLMRouter`.

- **prepare** is deterministic. It samples the candidate recipes the model will see, files every
  urgent pantry item under the candidates that use it, and writes the model's one user message.
  Dietary flags, the time cap, meals already planned and the six-week recency floor are applied
  here (V2 and V4), so the offered set is the dietary guarantee.
- **choose** is the only LLM step. It asks the model to pick from the candidates, and for the week's
  one-line summary, a reason kind per meal and one alternative per cube and per planned meal.
- **finalise** rejects anything the model was not offered (ids, already-planned meals, over-long
  lists, an alternative that is not an unused candidate) and writes the week's proposal: each meal's
  reason -- the model's prose without any sentence that dates something, then one sentence the server
  wrote -- plus `uses_up`, a `reason_kind`, and one alternative per card and per planned corpus meal.
- **degraded** is the fallback the graph writes when the model's answer keeps nothing: the sampler's
  best candidates with template text, every field of the proposal filled, flagged `degraded`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.llm import Feature
from glean.meal_plan.candidates import PantryItem, recipe_attributes, sample_corpus_candidates, urgent_pantry_uses
from glean.meal_plan.eligibility import CookedMeal
from glean.meal_plan.schemas import (
    CorpusMealPlanAlternative,
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanAlternative,
    MealPlanAttributes,
    MealPlanRequest,
    MealPlanResult,
    MealPlanSuggestion,
    PlannedMealAlternative,
    ReasonKind,
    UsedUpPantryItem,
)
from glean.observability import logger
from glean.recipes.attributes import DishType, MainCarb, MainProtein, RecipeAttributes

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
  fine; do not pad the list with weaker choices to reach the limit.
- Write week_summary as one line for the week as a whole, such as "Fish twice, and the coriander gets used".
- Give every meal a reason_kind: urgent_item (an item going off is why), profile, feedback, balance (the
  shape of the week), history (what the household cooked recently) or answer.
- Give every meal one alternative: another candidate you did not choose, with one sentence on why it works.
  Alternatives must differ from every meal you chose and from each other.
- If planned_meals lists meals already in the week, give each of them one alternative in
  planned_alternatives. Those meals are never chosen again: the week is topped up around them."""

# The whole corpus as one page, so an already-planned meal's title can be looked up without a read per id.
_ALL_RECIPES = 1_000_000
# Template text for a proposal the server had to write itself: spec §6.2's degraded fallback.
_TEMPLATE_MEAL_REASON = "A reliable pick for this week."
_TEMPLATE_ALTERNATIVE_REASON = "Another option from this week's shortlist."
NO_MEALS_WEEK_SUMMARY = "No dinners for this week."

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


class PlannedMeal(BaseModel):
    """A meal already in the week that came from the corpus.

    Generation tops up around it and never replaces it (ADR 0020), and it can still be swapped by the
    household, so the model is asked for one alternative per planned meal. An id the corpus does not
    hold is the app's own plan entry: it still blocks a pick, but there is no corpus recipe to swap it to.
    """

    external_id: str
    title: str


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
    titles: dict[str, str] = Field(
        default_factory=dict,
        description="Every offered external_id's title, so an alternative the server picks has one to show.",
    )
    planned: list[PlannedMeal] = Field(
        default_factory=list,
        description="The meals already in the week that came from the corpus, with their titles.",
    )
    attributes: dict[str, MealPlanAttributes] = Field(
        default_factory=dict,
        description=(
            "Per offered external_id, the labels its proposal card shows. Measured once, before the model "
            "chooses, so a chosen meal and an alternative the server picks both carry them."
        ),
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
    # One read of the corpus's answers for the whole proposal: the labels a card shows are facts about the
    # recipe, so they are measured here rather than asked of the model.
    measured = recipe_attributes(corpus, [candidate.summary for candidate in candidates])
    planned = _planned_corpus_meals(corpus, request.exclude_external_ids)
    logger.info(
        "generating corpus meal plan",
        extra={
            "pantry_items": len(request.pantry),
            "candidates": len(candidates),
            "urgent_pantry_items": len({item.name for items in urgent_uses.values() for item in items}),
            "planned_meals": len(planned),
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
        # Meals already in the week, which the model may offer an alternative for but never replace.
        "planned_meals": [meal.model_dump() for meal in planned],
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
        titles={candidate.external_id: candidate.title for candidate in candidates},
        planned=planned,
        attributes={
            candidate.external_id: _proposal_attributes(
                measured.get(candidate.external_id, RecipeAttributes()),
                total_time_mins=candidate.summary.total_time_mins,
            )
            for candidate in candidates
        },
    )


def _planned_corpus_meals(corpus: RecipeCorpusStore, excluded_ids: Sequence[str]) -> list[PlannedMeal]:
    """The already-planned meals the corpus holds, in the order the request listed them.

    One index read, not one blob read per id: this runs on every Generate and the list is short.
    """
    wanted = list(dict.fromkeys(excluded_ids))
    if not wanted:
        return []
    by_id = {summary.external_id: summary for summary in corpus.search(per_page=_ALL_RECIPES)[0]}
    return [
        PlannedMeal(external_id=external_id, title=by_id[external_id].title)
        for external_id in wanted
        if external_id in by_id
    ]


def choose(prepared: PreparedPlan, *, llm_router: LLMRouter, timeout_ms: int | None = None) -> CorpusMealPlanResponse:
    """Ask the model for the week: its picks, their alternatives and the one-line summary.

    Its answer is unvalidated; `finalise` judges every id in it. *timeout_ms* bounds the call: the agent
    passes what is left of its 90 s budget, so one slow model cannot hold the run past the point where
    the worker can still write an outcome.
    """
    return llm_router.invoke(
        Feature.MEAL_PLAN_GENERATION,
        CorpusMealPlanResponse,
        system=CORPUS_MEAL_PLAN_SYSTEM_PROMPT,
        user=prepared.user,
        timeout_ms=timeout_ms,
    )


def finalise(prepared: PreparedPlan, draft: CorpusMealPlanResponse) -> MealPlanResult:
    """Keep only the choices that are valid, and write the week's proposal.

    Valid means: offered to the model (so the dietary decisions, the time cap and the recency floor
    held), not already in the plan (generation only tops up, ADR 0020), and no more than one per slot.
    An alternative that is not an unused candidate -- invented, already planned, or another slice of
    the same meal -- is dropped and replaced from the shortlist, so one bad id never costs the
    household its week.
    """
    offered = set(prepared.offered_ids)
    excluded = set(prepared.excluded_ids)
    invented = [pick.external_id for pick in draft.suggestions if pick.external_id not in offered]
    if invented:
        logger.error("corpus meal plan chose recipes that were not offered; dropping", extra={"external_ids": invented})
    planned = [pick.external_id for pick in draft.suggestions if pick.external_id in excluded]
    if planned:
        logger.error("corpus meal plan chose recipes already in the plan; dropping", extra={"external_ids": planned})
    kept = [pick for pick in draft.suggestions if pick.external_id in offered and pick.external_id not in excluded]
    if len(kept) > prepared.meals_per_week:
        logger.error(
            "corpus meal plan exceeded meals_per_week; truncating",
            extra={"returned": len(kept), "limit": prepared.meals_per_week},
        )
    choices = kept[: prepared.meals_per_week]
    chosen = _reconciled(choices, prepared)
    unavailable = excluded | {suggestion.external_id for suggestion in chosen if suggestion.external_id}
    suggestions: list[MealPlanSuggestion] = []
    for suggestion, pick in zip(chosen, choices, strict=True):
        alternative = _alternative_for(pick.alternative, prepared, unavailable=unavailable)
        if alternative is not None and alternative.external_id is not None:
            unavailable.add(alternative.external_id)
        suggestions.append(suggestion.model_copy(update={"alternative": alternative}))
    planned_alternatives = _planned_alternatives(draft, prepared, unavailable=unavailable)
    logger.info(
        "meal plan generated",
        extra={"count": len(suggestions), "planned_alternatives": len(planned_alternatives)},
    )
    return MealPlanResult(
        suggestions=suggestions,
        week_summary=_week_summary(draft.week_summary, count=len(suggestions)),
        planned_alternatives=planned_alternatives,
    )


def degraded(prepared: PreparedPlan) -> MealPlanResult:
    """The fallback proposal: the best candidates the sampler offered, with template text throughout.

    Spec §6.2's fallback, for a run whose model step gave nothing usable (and, from V7, one that spent
    its budget or errored). It is a proposal like any other -- a summary, a reason kind per meal, an
    alternative per card and per planned meal -- so the household cannot tell; `degraded` and the logs
    are the only record (spec §6.5).
    """
    draft = CorpusMealPlanResponse(
        week_summary="",
        suggestions=[
            CorpusMealPlanRecipe(
                external_id=external_id,
                title=prepared.titles.get(external_id, external_id),
                reason=_TEMPLATE_MEAL_REASON,
                reason_kind=ReasonKind.URGENT_ITEM if _urgent_items(prepared, external_id) else ReasonKind.BALANCE,
            )
            for external_id in prepared.offered_ids[: prepared.meals_per_week]
        ],
    )
    result = finalise(prepared, draft)
    logger.warning("meal plan fell back to the sampler's picks", extra={"count": len(result.suggestions)})
    return result.model_copy(update={"degraded": True})


def _week_summary(summary: str, *, count: int) -> str:
    """The model's line, kept to one line, or template text: a corpus proposal's summary is never blank."""
    line = " ".join(summary.split())
    if line:
        return line
    if count == 0:
        return NO_MEALS_WEEK_SUMMARY
    if count == 1:
        return "One dinner for this week."
    return f"{count} dinners for this week."


def _alternative_for(
    model_alternative: CorpusMealPlanAlternative | None,
    prepared: PreparedPlan,
    *,
    unavailable: set[str],
) -> MealPlanAlternative | None:
    """The model's alternative when it is an unused candidate, else the next-best one nothing else uses."""
    if model_alternative is not None:
        if (
            model_alternative.external_id in set(prepared.offered_ids)
            and model_alternative.external_id not in unavailable
        ):
            return _as_alternative(_suggestion_for(model_alternative, prepared))
        logger.error(
            "dropping an alternative that is not an unused candidate",
            extra={"external_id": model_alternative.external_id},
        )
    spare = next((external_id for external_id in prepared.offered_ids if external_id not in unavailable), None)
    if spare is None:
        return None
    return _as_alternative(_template_alternative(prepared, spare))


def _planned_alternatives(
    draft: CorpusMealPlanResponse,
    prepared: PreparedPlan,
    *,
    unavailable: set[str],
) -> list[PlannedMealAlternative]:
    """One alternative per planned corpus meal, so a meal already in the week can be swapped too."""
    planned_ids = {meal.external_id for meal in prepared.planned}
    offered = {entry.planned_external_id: entry.alternative for entry in draft.planned_alternatives}
    unknown = sorted(set(offered) - planned_ids)
    if unknown:
        logger.error(
            "dropping alternatives for meals that are not corpus meals in the plan", extra={"external_ids": unknown}
        )
    entries: list[PlannedMealAlternative] = []
    for meal in prepared.planned:
        alternative = _alternative_for(offered.get(meal.external_id), prepared, unavailable=unavailable)
        if alternative is None or alternative.external_id is None:
            continue
        unavailable.add(alternative.external_id)
        entries.append(
            PlannedMealAlternative(
                external_id=meal.external_id, alternative=MealPlanSuggestion(**alternative.model_dump())
            )
        )
    return entries


def _as_alternative(suggestion: MealPlanSuggestion) -> MealPlanAlternative:
    """A swap target: the same line, without an alternative of its own."""
    return MealPlanAlternative(**suggestion.model_dump(exclude={"alternative"}))


def _template_alternative(prepared: PreparedPlan, external_id: str) -> MealPlanSuggestion:
    """An alternative the server picked -- the next-best candidate -- with template reason text."""
    items = _urgent_items(prepared, external_id)
    return _suggestion_for(
        CorpusMealPlanAlternative(
            external_id=external_id,
            title=prepared.titles.get(external_id, external_id),
            reason=_TEMPLATE_ALTERNATIVE_REASON,
            reason_kind=ReasonKind.URGENT_ITEM if items else ReasonKind.BALANCE,
        ),
        prepared,
    )


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
    return [_suggestion_for(meal, prepared) for meal in chosen]


def _suggestion_for(
    meal: CorpusMealPlanRecipe | CorpusMealPlanAlternative, prepared: PreparedPlan
) -> MealPlanSuggestion:
    """One meal as a proposal line: the reason with its canonical expiry sentence, plus `uses_up`."""
    items = _urgent_items(prepared, meal.external_id)
    reason = meal.reason
    if items:
        reason = _canonical_reason(reason, items, reference_date=prepared.reference_date)
    return MealPlanSuggestion(
        external_id=meal.external_id,
        title=meal.title,
        reason=reason,
        uses_up=[_used_up(item, reference_date=prepared.reference_date) for item in items],
        reason_kind=meal.reason_kind,
        attributes=prepared.attributes.get(meal.external_id, MealPlanAttributes()),
    )


def _proposal_attributes(attributes: RecipeAttributes, *, total_time_mins: int | None) -> MealPlanAttributes:
    """What a proposal card may label: the known values, and the time the card should show.

    `unsure` is not a label: a value the model was not confident about is left null so the card shows no chip.
    The time is the same number the household's cap is compared against: the active-time bucket's upper bound,
    capped by the recipe's total time (hands-on work cannot outlast the recipe), and total time alone when no
    bucket is known (not enriched yet, below its bar, or `60+`, which has no upper bound).
    """
    return MealPlanAttributes(
        main_protein=None if attributes.main_protein is MainProtein.UNSURE else attributes.main_protein,
        main_carb=None if attributes.main_carb is MainCarb.UNSURE else attributes.main_carb,
        dish_type=None if attributes.dish_type is DishType.UNSURE else attributes.dish_type,
        active_time_mins=attributes.active_time_mins(total_time_mins),
    )


def _urgent_items(prepared: PreparedPlan, external_id: str) -> list[UrgentUse]:
    """The urgent pantry items a recipe uses, soonest to go off first."""
    return sorted(
        prepared.urgent_uses.get(external_id, ()),
        key=lambda urgent_item: (urgent_item.expires_in_days or 0, urgent_item.name.casefold()),
    )


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
