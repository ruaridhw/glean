from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.llm import Feature
from glean.observability import logger, tracer
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

if TYPE_CHECKING:
    from glean.llm import LLMRouter


SHOPPING_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
Turn a user's natural-language shopping list into structured shopping item proposals.

Return structured data containing shopping item proposals and any clarifying questions.

Rules:
- Use concise grocery names suitable for a shopping list.
- Use quantity as a number.
- Use practical shopping units such as "g", "ml", "units", "pack", "bottle", "bag", or "box".
- When the user did not specify an amount, choose a sensible shopping-list default such as quantity 1 and unit "units".
- Set unit_price to null unless the user explicitly provides enough pricing detail.
- Set category to a broad grocery category when obvious, otherwise null.
- Set confidence from 0.0 to 1.0.
- For ambiguous phrases, either return a reasonable concrete item with lower confidence or add a clarifying question.
- Do not include markdown or explanatory text."""


@tracer.capture_method
def parse_shopping_description(
    request: ShoppingParseRequest,
    *,
    llm_router: LLMRouter,
) -> ShoppingParseResponse:
    logger.info("parsing shopping description", extra={"text_length": len(request.text)})
    response = llm_router.invoke(
        Feature.SHOPPING_LIST_DESCRIPTION,
        ShoppingParseResponse,
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {request.text}"),
        ],
    )
    logger.info("shopping description parsed", extra={"items": len(response.items)})
    return response
