"""Schema-contract tests: recorded model payloads must validate into the typed response as expected.

These replay canned outputs, so they say nothing about parser quality (the prompt is not exercised).
Parser quality is measured by the live eval in tests/integration/evals/test_shopping_list_description.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse
from glean.shopping.service import parse_shopping_description

_CASES = json.loads((Path(__file__).parents[1] / "fixtures" / "shopping_schema_contract_cases.json").read_text())


class _ReplayRouter:
    """Replays a recorded model payload through the same validation the real router applies."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def invoke(self, _feature: object, schema: type[ShoppingParseResponse], _messages: object) -> ShoppingParseResponse:
        return schema.model_validate(self.payload)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case["id"])
def test_recorded_model_payload_validates_into_the_typed_response(case: dict[str, object]) -> None:
    response = parse_shopping_description(
        ShoppingParseRequest(text=case["text"]), llm_router=_ReplayRouter(case["model_output"])
    )

    assert [[item.name, item.quantity, item.unit] for item in response.items] == case["expect"]["items"]
    assert len(response.clarifying_questions) == case["expect"]["questions"]
    for item in response.items:
        assert item.unit_price is None
        assert item.api_ingredient_id is None


def test_a_hallucinated_api_ingredient_id_fails_validation() -> None:
    payload = {
        "items": [
            {"name": "milk", "quantity": 1, "unit": "bottle", "confidence": 0.9, "api_ingredient_id": "ingredient:milk"}
        ]
    }

    with pytest.raises(ValidationError):
        ShoppingParseResponse.model_validate(payload)
