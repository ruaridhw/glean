from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.llm import Feature
from glean.observability import logger, tracer
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

if TYPE_CHECKING:
    from glean.decisions import DecisionClient
    from glean.llm import LLMRouter
    from glean.recipe_api.blob_store import BlobStore

_UNIT_SEPARATOR = re.compile(r"[,;\n]|&|\band\b", re.IGNORECASE)


# Units, categories, confidence range and the inactive fields are enforced by the response schema
# (see ShoppingProposalItem); this prompt only carries the task and how to handle ambiguity.
SHOPPING_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
Turn a user's natural-language shopping list into shopping item proposals.

The app cannot answer questions back yet, so always propose items: never return an empty items list.

- Use concise grocery names suitable for a shopping list.
- When the user did not specify an amount, choose a sensible default of one.
- When the user names a dish or meal instead of listing items (e.g. "tacos", "roast dinner"), propose the typical
  ingredients to buy for it as separate items, each with confidence of 0.6 or lower.
- For other ambiguous phrases, propose the most reasonable concrete item with lower confidence.
- clarifying_questions are optional hints shown alongside the proposed items; only add one when a choice
  would materially change the list."""


def split_into_units(text: str) -> list[str]:
    """Split a shopping description into the discrete phrases that each name something to buy."""
    return [unit for part in _UNIT_SEPARATOR.split(text) if (unit := part.strip())]


@tracer.capture_method
def parse_shopping_description(
    request: ShoppingParseRequest,
    *,
    llm_router: LLMRouter,
    decision_client: DecisionClient,
    cache: BlobStore,
) -> ShoppingParseResponse:
    first_spelling: dict[str, str] = {}
    for unit in split_into_units(request.text):
        first_spelling.setdefault(_unit_key(unit), unit)
    units = list(first_spelling.values())
    logger.info("parsing shopping description", extra={"text_length": len(request.text), "units": len(units)})
    parsed = [_parse_unit_cached(unit, llm_router=llm_router, cache=cache) for unit in units]
    merged = ShoppingParseResponse(items=[item for response in parsed for item in response.items])
    logger.info("shopping description parsed", extra={"items": len(merged.items)})
    return merged


def _unit_key(unit: str) -> str:
    return " ".join(unit.lower().split())


def _cache_path(unit: str) -> str:
    return f"shopping_parse/{hashlib.sha256(_unit_key(unit).encode()).hexdigest()}.json"


def _parse_unit_cached(unit: str, *, llm_router: LLMRouter, cache: BlobStore) -> ShoppingParseResponse:
    path = _cache_path(unit)
    if (hit := cache.read(path)) is not None:
        return ShoppingParseResponse.model_validate_json(hit)
    response = _parse_unit(unit, llm_router=llm_router)
    # food_group and api_ingredient_id are computed on read, so only stored fields are cached.
    cache.write(path, response.model_dump_json(exclude={"items": {"__all__": {"food_group", "api_ingredient_id"}}}))
    return response


def _parse_unit(unit: str, *, llm_router: LLMRouter) -> ShoppingParseResponse:
    return llm_router.invoke(
        Feature.SHOPPING_LIST_DESCRIPTION,
        ShoppingParseResponse,
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {unit}"),
        ],
    )
