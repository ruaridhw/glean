"""Normalisation (#123): turn raw names into catalogue items.

Order of work for a call: catalogue lookup, then one decision request per remaining name (match against a
shortlist, ingredient group, form, perishable), then one batched LLM call that names whatever nothing matched.
The store is the only cache; everything runs inside the request.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from glean.catalogue.groups import GROUPS, Form, GroupId, Kind
from glean.catalogue.models import CatalogueItem, name_key
from glean.catalogue.naming import NameRequest, name_items
from glean.catalogue.store import AliasConflictError
from glean.decisions import ChoiceQuestion, DecisionError, NoulCriteria, NoulQuestion
from glean.observability import logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glean.catalogue.store import CatalogueStore
    from glean.decisions import ChoiceAnswer, Decision, DecisionClient, Question
    from glean.llm import LLMRouter

# Lowest match probability that counts as a match. Set from the eval in docs/normalisation-eval.md.
MATCH_THRESHOLD = 0.7
MAX_NAMES = 20
NONE_OF_THESE = "none of these"
SHORTLIST_SIZE = 8
# Stop starting the naming call this long after normalise began, leaving room inside the 30 s request limit.
NAMING_BUDGET_S = 20.0
# The longest a single naming call may take (the LLM client's own default).
NAMING_CALL_TIMEOUT_S = 10.0


class Status(StrEnum):
    MATCHED = "matched"
    CREATED = "created"
    UNMATCHED = "unmatched"
    UNRESOLVED = "unresolved"


class ResultSource(StrEnum):
    CACHE = "cache"
    DECISION = "decision"
    LLM = "llm"


class ItemKind(StrEnum):
    INGREDIENT = "ingredient"
    HOUSEHOLD_ITEM = "household_item"


class NormalisedName(BaseModel):
    """What normalisation concluded for one raw name."""

    model_config = ConfigDict(frozen=True)

    input: str = Field(description="The name exactly as it was given.")
    catalogue_item_id: str | None = Field(description="The catalogue item the name resolved to, if any.")
    kind: ItemKind | None = Field(description="Whether the resolved item is an ingredient or a household item.")
    canonical_name: str = Field(description="The item's canonical name; the raw input when nothing resolved.")
    ingredient_group: GroupId | None = Field(description="The resolved item's ingredient group, if any.")
    form: Form | None = Field(description="The resolved item's form, if any.")
    perishable: bool | None = Field(description="Whether the item should be tracked as perishable, if known.")
    confidence: float = Field(ge=0.0, le=1.0, description="How sure the resolution is: 1 for a catalogue hit.")
    source: ResultSource = Field(
        description="Where the answer came from: the catalogue, the decision model or the LLM."
    )
    status: Status = Field(description="matched, created, unmatched, or unresolved (retry later).")


def _kind_of(group: GroupId) -> ItemKind:
    return ItemKind.HOUSEHOLD_ITEM if GROUPS[group].kind is Kind.HOUSEHOLD else ItemKind.INGREDIENT


def _result(
    raw: str,
    item: CatalogueItem,
    *,
    source: ResultSource,
    status: Status,
    confidence: float,
    perishable: bool | None = None,
) -> NormalisedName:
    return NormalisedName(
        input=raw,
        catalogue_item_id=item.id,
        kind=_kind_of(item.group),
        canonical_name=item.name,
        ingredient_group=item.group,
        form=item.form,
        perishable=item.tracking_mode.value == "perishable" if perishable is None else perishable,
        confidence=confidence,
        source=source,
        status=status,
    )


def _without_item(raw: str, *, status: Status, source: ResultSource) -> NormalisedName:
    return NormalisedName(
        input=raw,
        catalogue_item_id=None,
        kind=None,
        canonical_name=raw,
        ingredient_group=None,
        form=None,
        perishable=None,
        confidence=0.0,
        source=source,
        status=status,
    )


def questions_for(raw: str, shortlist: Sequence[CatalogueItem]) -> dict[str, Question]:
    questions: dict[str, Question] = {
        "ingredient_group": ChoiceQuestion(
            instructions=f"Which group does the item named {raw!r} belong to?",
            criteria={group.value: rules.name for group, rules in GROUPS.items()},
        ),
        "form": ChoiceQuestion(
            instructions=f"What form is the item named {raw!r} sold in?",
            criteria={form.value: form.value.replace("_", "/") for form in Form},
        ),
        "perishable": NoulQuestion(
            instructions=f"Does the item named {raw!r} go off within days of being bought or opened?",
            criteria=NoulCriteria(true="It is perishable.", false="It keeps for weeks or longer."),
        ),
    }
    if shortlist:
        options = {item.name: f"{item.name} ({GROUPS[item.group].name})" for item in shortlist}
        options[NONE_OF_THESE] = "None of the other options is the same item as the name."
        questions["match"] = ChoiceQuestion(
            instructions=f"Which catalogue item is the same product as the name {raw!r}?", criteria=options
        )
    return questions


def _decide(
    raw: str, context: str | None, shortlist: Sequence[CatalogueItem], decisions: DecisionClient
) -> Decision | None:
    state = {"name": raw, "context": context, "shortlist": [item.name for item in shortlist]}
    try:
        return decisions.decide(state, questions_for(raw, shortlist))
    except DecisionError:
        logger.exception("decision request failed", extra={"name_length": len(raw)})
        return None


def _form_for(group: GroupId, answer: ChoiceAnswer) -> Form:
    """The most probable form the group allows; formless groups only have not_applicable."""
    allowed = GROUPS[group].allowed_forms
    if len(allowed) == 1:
        return allowed[0]
    return max(allowed, key=lambda form: answer.probabilities.get(form.value, 0.0))


class _Miss(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw: str
    group: GroupId
    form: Form
    perishable: bool


def _confident_match(decision: Decision, group: GroupId, store: CatalogueStore) -> CatalogueItem | None:
    """The shortlisted item the decision picked, if it is probable enough and of the same kind as the group."""
    if "match" not in decision.answers:
        return None
    match = decision.choice("match")
    if match.choice == NONE_OF_THESE or match.probabilities[match.choice] < MATCH_THRESHOLD:
        return None
    item = store.get_by_name(match.choice)
    if item is None or GROUPS[item.group].kind is not GROUPS[group].kind:
        return None
    return item


def _create(miss: _Miss, canonical: str, store: CatalogueStore) -> NormalisedName:
    existing = store.get_by_name(canonical)
    if existing is None:
        try:
            item = store.create_provisional(canonical, miss.group, miss.form, aliases=(miss.raw,))
        except AliasConflictError:
            # Another request got there first with this name or alias: use its row.
            found = store.get_by_name(canonical) or store.get_by_name(miss.raw)
            if found is None:
                raise
            item = found
    else:
        item = existing
    if store.get_by_name(miss.raw) is None:
        item = store.upsert_alias(item.id, miss.raw)
    return _result(
        miss.raw,
        item,
        source=ResultSource.LLM,
        status=Status.MATCHED if existing is not None else Status.CREATED,
        confidence=1.0,
        perishable=miss.perishable,
    )


def _name_misses(
    misses: Sequence[_Miss], store: CatalogueStore, llm_router: LLMRouter, context: str | None, remaining_s: float
) -> dict[str, NormalisedName]:
    """Name every miss in one LLM call. A failed or skipped call leaves all of them unresolved, stored as nothing."""
    unresolved = {m.raw: _without_item(m.raw, status=Status.UNRESOLVED, source=ResultSource.LLM) for m in misses}
    if not misses or remaining_s <= 0:
        return unresolved
    requests = [NameRequest(input=m.raw, group=GROUPS[m.group].name) for m in misses]
    timeout_ms = int(min(remaining_s, NAMING_CALL_TIMEOUT_S) * 1000)
    try:
        named = name_items(requests, llm_router=llm_router, context=context, timeout_ms=timeout_ms)
    except Exception:
        logger.exception("naming call failed", extra={"names": len(misses)})
        return unresolved
    results = dict(unresolved)
    for miss in misses:
        if miss.raw not in named:
            continue
        canonical = (named[miss.raw] or "").strip()
        if canonical:
            results[miss.raw] = _create(miss, canonical, store)
        else:
            store.record_unmatched(miss.raw)
            results[miss.raw] = _without_item(miss.raw, status=Status.UNMATCHED, source=ResultSource.LLM)
    return results


def normalise(
    names: Sequence[str],
    *,
    store: CatalogueStore,
    decisions: DecisionClient,
    llm_router: LLMRouter,
    context: str | None = None,
    naming_budget_s: float = NAMING_BUDGET_S,
) -> list[NormalisedName]:
    """Resolve each name, in order. Raises ValueError for more than MAX_NAMES names."""
    if len(names) > MAX_NAMES:
        raise ValueError(f"At most {MAX_NAMES} names per call, got {len(names)}")
    started = time.monotonic()
    results: dict[str, NormalisedName] = {}
    pending: dict[str, str] = {}
    for raw in names:
        key = name_key(raw)
        if key in results or key in pending:
            continue
        item = store.get_by_name(raw)
        if item is not None:
            results[key] = _result(raw, item, source=ResultSource.CACHE, status=Status.MATCHED, confidence=1.0)
        elif store.is_unmatched(raw):
            results[key] = _without_item(raw, status=Status.UNMATCHED, source=ResultSource.CACHE)
        else:
            pending[key] = raw

    shortlists = {key: store.shortlist(raw, SHORTLIST_SIZE) for key, raw in pending.items()}
    with ThreadPoolExecutor(max_workers=max(1, len(pending))) as pool:
        futures = {key: pool.submit(_decide, raw, context, shortlists[key], decisions) for key, raw in pending.items()}
    misses: dict[str, _Miss] = {}
    for key, raw in pending.items():
        decision = futures[key].result()
        if decision is None:
            results[key] = _without_item(raw, status=Status.UNRESOLVED, source=ResultSource.DECISION)
            continue
        group = GroupId(decision.choice("ingredient_group").choice)
        perishable = decision.noul("perishable").noul >= 0.5
        item = _confident_match(decision, group, store)
        if item is None:
            form = _form_for(group, decision.choice("form"))
            misses[key] = _Miss(raw=raw, group=group, form=form, perishable=perishable)
            continue
        item = store.upsert_alias(item.id, raw)
        confidence = decision.choice("match").probabilities[item.name]
        results[key] = _result(
            raw, item, source=ResultSource.DECISION, status=Status.MATCHED, confidence=confidence, perishable=perishable
        )

    remaining_s = naming_budget_s - (time.monotonic() - started)
    named = _name_misses(list(misses.values()), store, llm_router, context, remaining_s)
    for key, miss in misses.items():
        results[key] = named[miss.raw]
    return [results[name_key(raw)].model_copy(update={"input": raw}) for raw in names]
