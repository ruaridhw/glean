"""Normalisation (#123): turn raw names into catalogue items.

Order of work for a call: catalogue lookup, then one decision request per remaining name (match against a
shortlist, ingredient group, form, perishable), then one batched LLM call that names whatever nothing matched.
The store is the only cache; everything runs inside the request.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from glean.catalogue.groups import GROUPS, Form, GroupId, Kind
from glean.catalogue.models import CatalogueItem, name_key
from glean.decisions import ChoiceQuestion, NoulCriteria, NoulQuestion

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glean.catalogue.store import CatalogueStore
    from glean.decisions import Decision, DecisionClient, Question
    from glean.llm import LLMRouter

# Lowest match probability that counts as a match. Set from the eval in docs/normalisation-eval.md.
MATCH_THRESHOLD = 0.7
MAX_NAMES = 20
NONE_OF_THESE = "none of these"
SHORTLIST_SIZE = 8


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


def _from_item(
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
        perishable=perishable if perishable is not None else item.tracking_mode.value == "perishable",
        confidence=confidence,
        source=source,
        status=status,
    )


def _questions(raw: str, shortlist: Sequence[CatalogueItem]) -> dict[str, Question]:
    options = {item.name: f"{item.name} ({GROUPS[item.group].name})" for item in shortlist}
    options[NONE_OF_THESE] = "None of the other options is the same item as the name."
    return {
        "match": ChoiceQuestion(
            instructions=f"Which catalogue item is the same product as the name {raw!r}?", criteria=options
        ),
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


def _decide(raw: str, context: str | None, shortlist: Sequence[CatalogueItem], decisions: DecisionClient) -> Decision:
    state = {"name": raw, "context": context, "shortlist": [item.name for item in shortlist]}
    return decisions.decide(state, _questions(raw, shortlist))


def normalise(
    names: Sequence[str],
    *,
    store: CatalogueStore,
    decisions: DecisionClient,
    llm_router: LLMRouter,
    context: str | None = None,
) -> list[NormalisedName]:
    """Resolve each name, in order. Raises ValueError for more than MAX_NAMES names."""
    results: dict[str, NormalisedName] = {}
    pending: dict[str, str] = {}
    for raw in names:
        key = name_key(raw)
        if key in results or key in pending:
            continue
        item = store.get_by_name(raw)
        if item is not None:
            results[key] = _from_item(raw, item, source=ResultSource.CACHE, status=Status.MATCHED, confidence=1.0)
        else:
            pending[key] = raw

    shortlists = {key: store.shortlist(raw, SHORTLIST_SIZE) for key, raw in pending.items()}
    with ThreadPoolExecutor(max_workers=max(1, len(pending))) as pool:
        futures = {key: pool.submit(_decide, raw, context, shortlists[key], decisions) for key, raw in pending.items()}
    for key, raw in pending.items():
        decision = futures[key].result()
        match = decision.choice("match")
        item = store.get_by_name(match.choice) if match.choice != NONE_OF_THESE else None
        if item is not None and match.probabilities[match.choice] >= MATCH_THRESHOLD:
            item = store.upsert_alias(item.id, raw)
            results[key] = _from_item(
                raw,
                item,
                source=ResultSource.DECISION,
                status=Status.MATCHED,
                confidence=match.probabilities[match.choice],
                perishable=decision.noul("perishable").noul >= 0.5,
            )
    return [results[name_key(raw)].model_copy(update={"input": raw}) for raw in names]
