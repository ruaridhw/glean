from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from glean.llm import Feature, message_content_as_text
from glean.observability import logger, tracer
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


SHOPPING_PARSE_SYSTEM_PROMPT = """You are a grocery shopping list parser for the Glean app.
Turn a user's natural-language shopping list into structured shopping item proposals.

Return ONLY valid JSON with this exact structure:
{
  "items": [
    {
      "name": "concise grocery item name",
      "quantity": 1,
      "unit": "units",
      "unit_price": null,
      "api_ingredient_id": null,
      "category": null,
      "confidence": 0.8
    }
  ],
  "clarifying_questions": []
}

Rules:
- Use concise grocery names suitable for a shopping list.
- Use quantity as a number.
- Use practical shopping units such as "g", "ml", "units", "pack", "bottle", "bag", or "box".
- When the user did not specify an amount, choose a sensible shopping-list default such as quantity 1 and unit "units".
- Set unit_price to null unless the user explicitly provides enough pricing detail.
- Set api_ingredient_id to null unless you can confidently map to an external ingredient ID from provided context.
- Set category to a broad grocery category when obvious, otherwise null.
- Set confidence from 0.0 to 1.0.
- For ambiguous phrases, either return a reasonable concrete item with lower confidence or add a clarifying question.
- Do not include markdown or explanatory text."""


@tracer.capture_method
def parse_shopping_description(
    request: ShoppingParseRequest,
    *,
    model: BaseChatModel,
) -> ShoppingParseResponse:
    logger.info("parsing shopping description", extra={"text_length": len(request.text)})
    result = model.invoke(
        [
            SystemMessage(content=SHOPPING_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this shopping list description: {request.text}"),
        ],
        config={"metadata": {"feature": Feature.SHOPPING_LIST_DESCRIPTION}},
    )
    response = ShoppingParseResponse(**json.loads(message_content_as_text(result.content)))
    logger.info("shopping description parsed", extra={"items": len(response.items)})
    return response
