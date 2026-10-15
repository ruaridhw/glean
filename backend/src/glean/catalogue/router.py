from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    SecretStr,
    StringConstraints,
)

from glean.catalogue.dynamo_store import DynamoCatalogueStore
from glean.catalogue.groups import GROUPS, Form, GroupId, GroupRules, Kind, StockUnit, TrackingMode
from glean.catalogue.models import CatalogueItem, ItemOverrides, Source, name_key
from glean.catalogue.normalise import MAX_NAMES, NormalisedName, normalise
from glean.catalogue.sections import Section  # noqa: TC001 - pydantic resolves this annotation at runtime.
from glean.catalogue.store import CatalogueStore  # noqa: TC001 - FastAPI resolves this via Depends at runtime.
from glean.config import Settings, get_settings
from glean.decisions import DecisionClient
from glean.dependencies import get_llm_router, verify_cognito_token
from glean.llm import LLMRouter  # noqa: TC001 - FastAPI resolves this via Depends at runtime.
from glean.rate_limit import enforce_ai_rate_limit

router = APIRouter(prefix="/catalogue", tags=["catalogue"], dependencies=[Depends(verify_cognito_token)])


def _not_blank(name: str) -> str:
    # The raw text is kept as written; only a name with nothing in it is refused.
    if not name.strip():
        raise ValueError("A name can't be blank")
    return name


type RawName = Annotated[str, StringConstraints(max_length=200), AfterValidator(_not_blank)]


class NormaliseRequest(BaseModel):
    names: list[RawName] = Field(
        min_length=1, max_length=MAX_NAMES, description=f"Raw names to resolve, at most {MAX_NAMES} per call."
    )
    context: str | None = Field(
        default=None,
        max_length=200,
        description="Where the names came from, e.g. 'receipt line'; a hint for the models.",
    )


class NormaliseResponse(BaseModel):
    results: list[NormalisedName] = Field(
        description="One result per requested name, in order. Retry unresolved names later; everything else is final."
    )


class SyncGroup(BaseModel):
    id: GroupId = Field(description="Stable group id.")
    name: str = Field(description="Plain-English display name of the group.")
    kind: Kind = Field(description="Whether items in the group are ingredients or household items.")
    food_group: str = Field(description="The one food group the meal plan counts the group towards.")
    tracking_mode: TrackingMode = Field(description="Default tracking mode for items in the group.")
    stock_unit: StockUnit | None = Field(description="Default stock unit; null unless the group is counted.")
    allowed_forms: list[Form] = Field(description="The forms an item in the group may take.")
    unopened_shelf_life_days: dict[Form, int | None] = Field(
        description="Default unopened shelf life, per allowed form. Null where the group never expires."
    )
    once_opened_shelf_life_days: dict[Form, int | None] = Field(
        description="Default once-opened shelf life, per allowed form. Null where an opened pack has no limit."
    )


class SyncItem(BaseModel):
    id: str = Field(description="Stable id, unique within the catalogue. Never reused or replaced.")
    name: str = Field(description="The canonical name.")
    group: GroupId = Field(description="The ingredient group the item takes its default rules from.")
    form: Form = Field(description="The form the ingredient is sold and kept in.")
    overrides: ItemOverrides = Field(description="Per-item changes to the group's rules; null fields use the group's.")
    section: Section = Field(description="The store section the item is found in, from its group and form.")
    former_ids: list[str] = Field(
        description="Ids of items merged into this one; a device resolves each to this item. Empty when none."
    )
    density_g_per_ml: float | None = Field(description="Density in g/ml, where known.")
    source: Source = Field(description="Whether the item came from the seed or was added provisionally by an LLM.")


class SyncAlias(BaseModel):
    key: str = Field(description="The name, case-folded and whitespace-collapsed: what a lookup matches on.")
    name: str = Field(description="The name as written.")
    item_id: str = Field(description="The catalogue item the name resolves to.")


class CatalogueSyncResponse(BaseModel):
    version: int = Field(description="The catalogue version this response brings a device up to. Send it as `since`.")
    groups: list[SyncGroup] = Field(
        description="Every ingredient group, every time: groups are fixed by the backend release, not versioned."
    )
    items: list[SyncItem] = Field(description="Items written after `since`. Empty when the device is up to date.")
    aliases: list[SyncAlias] = Field(
        description="Every name, canonical name included, of the items sent. Upsert by `key`."
    )


def _sync_group(group_id: GroupId, rules: GroupRules) -> SyncGroup:
    return SyncGroup(
        id=group_id,
        name=rules.name,
        kind=rules.kind,
        food_group=rules.food_group.value,
        tracking_mode=rules.tracking_mode,
        stock_unit=rules.stock_unit,
        allowed_forms=list(rules.allowed_forms),
        unopened_shelf_life_days=dict(rules.unopened_shelf_life_days),
        once_opened_shelf_life_days=dict(rules.once_opened_shelf_life_days),
    )


def _sync_aliases(item: CatalogueItem) -> list[SyncAlias]:
    names = {name_key(name): name for name in (*reversed(item.aliases), item.name)}
    return [SyncAlias(key=key, name=name, item_id=item.id) for key, name in sorted(names.items())]


@lru_cache(maxsize=2)
def _dynamo_store(table_name: str, region: str) -> DynamoCatalogueStore:
    return DynamoCatalogueStore(table_name, region=region)


def get_catalogue_store(settings: Annotated[Settings, Depends(get_settings)]) -> CatalogueStore:
    if not settings.catalogue_table:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="The catalogue is not configured")
    return _dynamo_store(settings.catalogue_table, settings.aws_region)


@lru_cache(maxsize=1)
def _decision_client(api_key: SecretStr) -> DecisionClient:
    return DecisionClient(api_key=api_key)


def get_decision_client(settings: Annotated[Settings, Depends(get_settings)]) -> DecisionClient:
    return _decision_client(settings.openrouter_api_key)


@router.post("/normalise", response_model=NormaliseResponse, dependencies=[Depends(enforce_ai_rate_limit)])
def normalise_names(
    request: NormaliseRequest,
    store: Annotated[CatalogueStore, Depends(get_catalogue_store)],
    decisions: Annotated[DecisionClient, Depends(get_decision_client)],
    llm_router: Annotated[LLMRouter, Depends(get_llm_router)],
) -> NormaliseResponse:
    results = normalise(request.names, store=store, decisions=decisions, llm_router=llm_router, context=request.context)
    return NormaliseResponse(results=results)


@router.get("", response_model=CatalogueSyncResponse)
def sync_catalogue(
    store: Annotated[CatalogueStore, Depends(get_catalogue_store)],
    since: Annotated[int, Query(ge=0, description="The catalogue version the device holds; 0 is everything.")] = 0,
) -> CatalogueSyncResponse:
    changes = store.changes_since(since)
    return CatalogueSyncResponse(
        version=changes.version,
        groups=[_sync_group(group_id, rules) for group_id, rules in GROUPS.items()],
        items=[
            SyncItem(
                id=item.id,
                name=item.name,
                group=item.group,
                form=item.form,
                overrides=item.overrides,
                section=item.section,
                former_ids=list(item.former_ids),
                density_g_per_ml=item.density_g_per_ml,
                source=item.source,
            )
            for item in changes.items
        ],
        aliases=[alias for item in changes.items for alias in _sync_aliases(item)],
    )
