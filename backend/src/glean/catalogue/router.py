from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    SecretStr,
    StringConstraints,
)

from glean.catalogue.dynamo_store import DynamoCatalogueStore
from glean.catalogue.normalise import MAX_NAMES, NormalisedName, normalise
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
