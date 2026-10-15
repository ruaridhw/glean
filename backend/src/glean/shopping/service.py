from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.decisions import DECISION_MODEL, DecisionError, NoulCriteria, NoulQuestion
from glean.llm import Feature
from glean.observability import logger, tracer
from glean.shopping.schemas import (
    ShoppingBatchParseResponse,
    ShoppingParseRequest,
    ShoppingParseResponse,
    ShoppingProposalItem,
    ShoppingUnit,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.decisions import DecisionClient
    from glean.llm import LLMRouter
    from glean.recipe_api.blob_store import BlobStore


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

BATCH_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
The user's shopping list was split into numbered phrases, each tagged with how to treat it. Answer every phrase
exactly once, by its number.

- [dish]: the phrase names a dish or meal. Propose the typical ingredients to buy for it as separate items, each
  with confidence of 0.6 or lower.
- [item]: the phrase names a grocery item or product. Propose it as one item; do not break it into other items.
- [unsure]: if the phrase names a dish or meal, treat it as [dish]; for other ambiguous phrases, propose the most
  reasonable concrete item with lower confidence.

- Use concise grocery names suitable for a shopping list.
- When the user did not specify an amount, choose a sensible default of one.
- clarifying_questions are optional hints shown alongside the proposed items; only add one when a choice
  would materially change the list."""

# Whole-request time budget. The app and API Gateway give up at 30 s, so this leaves room for the response, and
# whatever isn't finished by the end of a phase degrades to the single-call parse instead of failing.
REQUEST_BUDGET_S = 20.0
_PLAN_SHARE = 0.25  # cache reads and decisions must finish within this share of the budget
_BATCH_SHARE = 0.8  # the batch call must finish within this share, leaving the rest for the fallback
_MODEL_TIMEOUT_S = 10.0
_MAX_PARALLEL = 16

_DISH_QUESTION = NoulQuestion(
    instructions="Does this phrase name a dish or meal to cook, rather than a grocery item to buy?",
    criteria=NoulCriteria(
        true="The phrase names a dish or meal, e.g. tacos, roast dinner, spaghetti bolognese.",
        false="The phrase names a grocery item or product, e.g. milk, 2 bananas, washing-up liquid.",
    ),
)
_LIST_QUESTION = NoulQuestion(
    instructions="Does this phrase list several separate things to buy, rather than naming one dish, meal or product?",
    criteria=NoulCriteria(
        true="The phrase lists separate things to buy, e.g. milk and eggs, apples and pears.",
        false="The phrase names one dish, meal or product, even if its name contains 'and', e.g. mac and cheese.",
    ),
)
_DISH = "names_a_dish"
_LIST = "lists_several_items"
_QUESTIONS = {_DISH: _DISH_QUESTION, _LIST: _LIST_QUESTION}

# Thresholds come from tests/fixtures/shopping_gate_sample.json: 40 labelled phrases scored live by the pinned
# decision model. Each errs towards the safe fallback (the "unsure" treatment, or keeping a phrase whole).
# - dish >= 0.8: every labelled dish scored >= 0.82 (mac and cheese; margin 0.02); the highest non-dish scored
#   0.74 (rice and beans; margin 0.06), so nothing labelled a product or list is expanded into ingredients.
# - item <= 0.2: every labelled item or product scored <= 0.16 (sweet and sour sauce; margin 0.04); the next
#   phrase up scored 0.41 (crisps and dip; margin 0.21), and the lowest dish 0.82.
# - list >= 0.45: every labelled list scored >= 0.52 (crisps and dip; margin 0.07); the highest compound dish or
#   product scored 0.15 (fish & chips; margin 0.30). A segment is split only when it also isn't a dish.
_DISH_AT_LEAST = 0.8
_ITEM_AT_MOST = 0.2
_LIST_AT_LEAST = 0.45

# Segments end at commas (but not decimal commas), semicolons and newlines. "and" and "&" only split a segment
# after the decision model says it lists separate items: they also appear inside "mac and cheese".
_LIST_SEPARATOR = re.compile(r"[;\n]|(?<!\d),|,(?!\d)")
_CONJUNCTION = re.compile(r"\s*&\s*|\s+and\s+", re.IGNORECASE)
_LEADING_CONJUNCTION = re.compile(r"^(?:and|&)\s+", re.IGNORECASE)


@dataclass
class _Unit:
    phrase: str
    treatment: str = "unsure"


@dataclass
class _Plan:
    """A segment of the description, the phrases it is parsed as, and whether every decision was available."""

    segment: str
    units: list[_Unit]
    decided: bool


def split_into_segments(text: str) -> list[str]:
    """Split a shopping description at list separators into the segments that each name something to buy."""
    parts = (_LEADING_CONJUNCTION.sub("", part.strip()) for part in _LIST_SEPARATOR.split(text))
    return [part for part in parts if part]


def _unit_key(unit: str) -> str:
    return " ".join(unit.lower().split())


def _behaviour_version(llm_router: LLMRouter) -> str:
    """Fingerprint of everything that shapes a parse, so a change to any of it misses old cache entries."""
    behaviour = {
        "prompts": [BATCH_PARSE_SYSTEM_PROMPT, SHOPPING_PARSE_SYSTEM_PROMPT],
        "schemas": [ShoppingBatchParseResponse.model_json_schema(), ShoppingParseResponse.model_json_schema()],
        "units": [unit.value for unit in ShoppingUnit],
        "decision": [
            DECISION_MODEL,
            {name: question.model_dump() for name, question in _QUESTIONS.items()},
            [_DISH_AT_LEAST, _ITEM_AT_MOST, _LIST_AT_LEAST],
        ],
        "segmentation": [_LIST_SEPARATOR.pattern, _CONJUNCTION.pattern, _LEADING_CONJUNCTION.pattern],
        "llm_model": llm_router.model_id_for(Feature.SHOPPING_LIST_DESCRIPTION),
    }
    return hashlib.sha256(json.dumps(behaviour, sort_keys=True, default=str).encode()).hexdigest()


def _cache_path(version: str, segment: str) -> str:
    return f"{version}/{hashlib.sha256(_unit_key(segment).encode()).hexdigest()}.json"


def _collect[ItemT, ResultT](
    pool: ThreadPoolExecutor, work: Callable[[ItemT], ResultT], items: Sequence[ItemT], until: float
) -> list[ResultT | None]:
    """Run `work` over `items` in parallel; whatever fails or isn't done by `until` (monotonic time) is None."""
    futures = [pool.submit(work, item) for item in items]
    wait(futures, timeout=max(0.0, until - time.monotonic()))
    results: list[ResultT | None] = []
    for future in futures:
        if future.done() and not future.cancelled() and future.exception() is None:
            results.append(future.result())
            continue
        if future.done() and not future.cancelled():
            logger.warning("shopping parse step failed", exc_info=future.exception())
        future.cancel()
        results.append(None)
    return results


def _read_cached(cache: BlobStore, path: str) -> ShoppingParseResponse | None:
    try:
        entry = cache.read(path)
        return None if entry is None else ShoppingParseResponse.model_validate_json(entry)
    except Exception:  # malformed or unreachable (S3 transport errors aren't OSError): either way, just a miss
        logger.warning("shopping parse cache read failed", extra={"path": path}, exc_info=True)
        return None


def _write_cached(cache: BlobStore, path: str, response: ShoppingParseResponse) -> None:
    # food_group and api_ingredient_id are computed on read, so only stored fields are cached.
    entry = response.model_dump_json(exclude={"items": {"__all__": {"food_group", "api_ingredient_id"}}})
    try:
        cache.write(path, entry)
    except Exception:  # a cache outage must not fail the parse; S3 raises its own client errors
        logger.warning("shopping parse cache write failed", extra={"path": path}, exc_info=True)


def _decide(decision_client: DecisionClient, phrase: str, names: Sequence[str]) -> dict[str, float] | None:
    try:
        decision = decision_client.decide({"phrase": phrase}, {name: _QUESTIONS[name] for name in names})
    except DecisionError:
        logger.warning("shopping decision unavailable", exc_info=True)
        return None
    return {name: decision.noul(name).noul for name in names}


def _treatment(scores: dict[str, float] | None) -> str:
    if scores is None:
        return "unsure"
    if scores[_DISH] >= _DISH_AT_LEAST:
        return "dish"
    if scores[_DISH] <= _ITEM_AT_MOST:
        return "item"
    return "unsure"


def _lists_separate_items(scores: dict[str, float] | None) -> bool:
    return scores is not None and scores.get(_LIST, 0.0) >= _LIST_AT_LEAST and scores[_DISH] < _DISH_AT_LEAST


def _plan_segments(
    segments: Sequence[str], decision_client: DecisionClient, pool: ThreadPoolExecutor, until: float
) -> list[_Plan]:
    def first(segment: str) -> dict[str, float] | None:
        names = (_DISH, _LIST) if _CONJUNCTION.search(segment) else (_DISH,)
        return _decide(decision_client, segment, names)

    plans: list[_Plan] = []
    for segment, scores in zip(segments, _collect(pool, first, segments, until), strict=True):
        parts = [part for part in _CONJUNCTION.split(segment) if part.strip()]
        if _lists_separate_items(scores) and len(parts) > 1:
            plans.append(_Plan(segment, [_Unit(part.strip()) for part in parts], decided=False))
        else:
            plans.append(_Plan(segment, [_Unit(segment, _treatment(scores))], decided=scores is not None))

    split_units = [unit for plan in plans if len(plan.units) > 1 for unit in plan.units]
    scored = _collect(pool, lambda unit: _decide(decision_client, unit.phrase, (_DISH,)), split_units, until)
    for unit, scores in zip(split_units, scored, strict=True):
        unit.treatment = _treatment(scores)
    undecided = {id(unit) for unit, scores in zip(split_units, scored, strict=True) if scores is None}
    for plan in plans:
        if len(plan.units) > 1:
            plan.decided = not any(id(unit) in undecided for unit in plan.units)
    return plans


def _timeout_ms(until: float) -> int:
    return int(max(1.0, min(_MODEL_TIMEOUT_S, until - time.monotonic())) * 1000)


def _parse_batch(
    units: Sequence[_Unit], llm_router: LLMRouter, pool: ThreadPoolExecutor, until: float
) -> dict[int, tuple[list[ShoppingProposalItem], list[str]]]:
    """Parse every phrase in one structured call; returns what came back, by phrase number (from 1)."""
    listing = "\n".join(f"{number}. [{unit.treatment}] {unit.phrase}" for number, unit in enumerate(units, start=1))
    messages = [
        SystemMessage(content=BATCH_PARSE_SYSTEM_PROMPT),
        HumanMessage(content=f"Parse these numbered shopping list phrases:\n{listing}"),
    ]
    timeout_ms = _timeout_ms(until)

    def call() -> ShoppingBatchParseResponse:
        return llm_router.invoke(
            Feature.SHOPPING_LIST_DESCRIPTION, ShoppingBatchParseResponse, messages, request_timeout=timeout_ms
        )

    future = pool.submit(call)
    wait([future], timeout=max(0.0, until - time.monotonic()))
    if not future.done():
        future.cancel()
        logger.warning("shopping batch parse outlived its budget", extra={"phrases": len(units)})
        return {}
    try:
        response = future.result()
    except Exception:  # any model or validation failure degrades to the single-call parse
        logger.warning("shopping batch parse failed", exc_info=True)
        return {}
    answered: dict[int, tuple[list[ShoppingProposalItem], list[str]]] = {}
    for parsed in response.units:
        if 1 <= parsed.number <= len(units):
            answered.setdefault(parsed.number, (parsed.items, parsed.clarifying_questions))
    return answered


def _parse_single(llm_router: LLMRouter, text: str, until: float) -> ShoppingParseResponse:
    return llm_router.invoke(
        Feature.SHOPPING_LIST_DESCRIPTION,
        ShoppingParseResponse,
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {text}"),
        ],
        request_timeout=_timeout_ms(until),
    )


def _merge(parts: Sequence[ShoppingParseResponse]) -> ShoppingParseResponse:
    questions = dict.fromkeys(question for part in parts for question in part.clarifying_questions)
    return ShoppingParseResponse(
        items=[item for part in parts for item in part.items], clarifying_questions=list(questions)
    )


@tracer.capture_method
def parse_shopping_description(
    request: ShoppingParseRequest,
    *,
    llm_router: LLMRouter,
    decision_client: DecisionClient,
    cache: BlobStore,
    time_budget_s: float = REQUEST_BUDGET_S,
) -> ShoppingParseResponse:
    start = time.monotonic()
    end, plan_until, batch_until = (start + time_budget_s * share for share in (1.0, _PLAN_SHARE, _BATCH_SHARE))
    first_spelling: dict[str, str] = {}
    for segment in split_into_segments(request.text):
        first_spelling.setdefault(_unit_key(segment), segment)
    segments = list(first_spelling.values())
    logger.info("parsing shopping description", extra={"text_length": len(request.text), "segments": len(segments)})
    version = _behaviour_version(llm_router)

    pool = ThreadPoolExecutor(max_workers=_MAX_PARALLEL)
    try:
        cached = _collect(
            pool, lambda segment: _read_cached(cache, _cache_path(version, segment)), segments, plan_until
        )
        parsed: dict[str, ShoppingParseResponse] = {s: hit for s, hit in zip(segments, cached, strict=True) if hit}
        plans = _plan_segments([s for s in segments if s not in parsed], decision_client, pool, plan_until)

        units = [unit for plan in plans for unit in plan.units]
        answered = _parse_batch(units, llm_router, pool, batch_until) if units else {}
        degraded: list[_Plan] = []
        number = 1
        for plan in plans:
            numbers = range(number, number + len(plan.units))
            number += len(plan.units)
            if all(n in answered for n in numbers):
                parsed[plan.segment] = _merge(
                    [ShoppingParseResponse(items=answered[n][0], clarifying_questions=answered[n][1]) for n in numbers]
                )
            else:
                degraded.append(plan)

        writes = [(plan.segment, parsed[plan.segment]) for plan in plans if plan.decided and plan.segment in parsed]
        write_futures = [pool.submit(_write_cached, cache, _cache_path(version, s), response) for s, response in writes]
        fallback = _parse_single(llm_router, ", ".join(plan.segment for plan in degraded), end) if degraded else None
        wait(write_futures, timeout=max(0.0, end - time.monotonic()))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    merged = _merge([parsed[s] for s in segments if s in parsed] + ([fallback] if fallback else []))
    logger.info("shopping description parsed", extra={"items": len(merged.items), "degraded": len(degraded)})
    return merged
