from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.decisions import DECISION_MODEL, DecisionError, NoulCriteria, NoulQuestion
from glean.llm import Feature
from glean.observability import logger, tracer
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse, ShoppingUnit

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

ITEM_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
The user's phrase names a single grocery item (or a few like it). Propose it as one shopping item proposal;
do not break it into other items.

- Use a concise grocery name suitable for a shopping list.
- When the user did not specify an amount, choose a sensible default of one.
- When the phrase is vague, propose the most reasonable concrete item with lower confidence.
- clarifying_questions are optional hints shown alongside the proposed item; only add one when a choice
  would materially change the list."""

DISH_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
The user's phrase names a dish or meal rather than a grocery item. Propose the typical ingredients to buy for it
as separate shopping item proposals, each with confidence of 0.6 or lower.

- Use concise grocery names suitable for a shopping list.
- When an amount is not obvious, choose a sensible default of one.
- clarifying_questions are optional hints shown alongside the proposed items; only add one when a choice
  would materially change the list."""

# The decision model's answer is the probability that the phrase names a dish.
_DISH_QUESTION = NoulQuestion(
    instructions="Does this phrase name a dish or meal to cook, rather than a grocery item to buy?",
    criteria=NoulCriteria(
        true="The phrase names a dish or meal, e.g. tacos, roast dinner, spaghetti bolognese.",
        false="The phrase names a grocery item or product, e.g. milk, 2 bananas, washing-up liquid.",
    ),
)
_DISH_QUESTION_NAME = "names_a_dish"
_DISH_AT_LEAST = 0.7
_ITEM_AT_MOST = 0.3
_MAX_PARALLEL_UNITS = 8


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
    version = _behaviour_version(llm_router)

    def parse(unit: str) -> ShoppingParseResponse:
        return _parse_unit_cached(
            unit, version=version, llm_router=llm_router, decision_client=decision_client, cache=cache
        )

    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_UNITS) as pool:
        parsed = list(pool.map(parse, units))

    questions = list(dict.fromkeys(question for response in parsed for question in response.clarifying_questions))
    merged = ShoppingParseResponse(
        items=[item for response in parsed for item in response.items], clarifying_questions=questions
    )
    logger.info("shopping description parsed", extra={"items": len(merged.items)})
    return merged


def _unit_key(unit: str) -> str:
    return " ".join(unit.lower().split())


def _behaviour_version(llm_router: LLMRouter) -> str:
    """Fingerprint of everything that shapes a parse, so a change to any of it misses old cache entries."""
    behaviour = {
        "prompts": [SHOPPING_PARSE_SYSTEM_PROMPT, ITEM_PARSE_SYSTEM_PROMPT, DISH_PARSE_SYSTEM_PROMPT],
        "schema": ShoppingParseResponse.model_json_schema(),
        "units": [unit.value for unit in ShoppingUnit],
        "decision": [DECISION_MODEL, _DISH_QUESTION.model_dump(), _DISH_AT_LEAST, _ITEM_AT_MOST],
        "llm_model": llm_router.model_id_for(Feature.SHOPPING_LIST_DESCRIPTION),
    }
    return hashlib.sha256(json.dumps(behaviour, sort_keys=True, default=str).encode()).hexdigest()


def _cache_path(version: str, unit: str) -> str:
    return f"shopping_parse/{version}/{hashlib.sha256(_unit_key(unit).encode()).hexdigest()}.json"


def _parse_unit_cached(
    unit: str, *, version: str, llm_router: LLMRouter, decision_client: DecisionClient, cache: BlobStore
) -> ShoppingParseResponse:
    path = _cache_path(version, unit)
    if (cached := _read_cached(cache, path)) is not None:
        return cached
    prompt = _choose_prompt(unit, decision_client)
    response = _parse_unit(unit, prompt, llm_router=llm_router)
    if prompt is not None:
        _write_cached(cache, path, response)
    return response


def _read_cached(cache: BlobStore, path: str) -> ShoppingParseResponse | None:
    try:
        entry = cache.read(path)
        return None if entry is None else ShoppingParseResponse.model_validate_json(entry)
    except (OSError, ValueError):
        logger.warning("shopping parse cache entry unreadable", extra={"path": path}, exc_info=True)
        return None


def _write_cached(cache: BlobStore, path: str, response: ShoppingParseResponse) -> None:
    # food_group and api_ingredient_id are computed on read, so only stored fields are cached.
    entry = response.model_dump_json(exclude={"items": {"__all__": {"food_group", "api_ingredient_id"}}})
    try:
        cache.write(path, entry)
    except Exception:  # a cache outage must not fail the parse; S3 raises its own client errors
        logger.warning("shopping parse cache write failed", extra={"path": path}, exc_info=True)


def _choose_prompt(unit: str, decision_client: DecisionClient) -> str | None:
    """Pick the prompt for a unit from the dish-or-item decision, or None when the decision isn't available."""
    try:
        decision = decision_client.decide({"phrase": unit}, {_DISH_QUESTION_NAME: _DISH_QUESTION})
    except DecisionError:
        logger.warning("dish decision unavailable", exc_info=True)
        return None
    dish_probability = decision.noul(_DISH_QUESTION_NAME).noul
    if dish_probability >= _DISH_AT_LEAST:
        return DISH_PARSE_SYSTEM_PROMPT
    if dish_probability <= _ITEM_AT_MOST:
        return ITEM_PARSE_SYSTEM_PROMPT
    return SHOPPING_PARSE_SYSTEM_PROMPT


def _parse_unit(unit: str, prompt: str | None, *, llm_router: LLMRouter) -> ShoppingParseResponse:
    return llm_router.invoke(
        Feature.SHOPPING_LIST_DESCRIPTION,
        ShoppingParseResponse,
        [
            SystemMessage(content=prompt or SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {unit}"),
        ],
    )
