from __future__ import annotations

from glean.llm import Feature
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse
from glean.shopping.service import parse_shopping_description


class _FakeLLMRouter:
    def __init__(self, response: ShoppingParseResponse) -> None:
        self.response = response
        self.feature: Feature | None = None
        self.schema: type[object] | None = None
        self.messages: list[object] = []

    def invoke(self, feature: Feature, schema: type[object], messages: list[object]) -> ShoppingParseResponse:
        self.feature = feature
        self.schema = schema
        self.messages = messages
        return self.response


def test_parse_shopping_description_returns_proposed_items() -> None:
    llm_router = _FakeLLMRouter(
        ShoppingParseResponse(
            items=[
                {
                    "name": "taco shells",
                    "quantity": 1,
                    "unit": "pack",
                    "unit_price": None,
                    "category": "bakery",
                    "confidence": 0.82,
                },
                {
                    "name": "whole milk",
                    "quantity": 1,
                    "unit": "bottle",
                    "unit_price": None,
                    "category": "dairy",
                    "confidence": 0.91,
                },
            ],
            clarifying_questions=["What lunchbox snacks do you want?"],
        )
    )

    response = parse_shopping_description(
        ShoppingParseRequest(text="stuff for tacos, milk, and lunchbox snacks"),
        llm_router=llm_router,
    )

    assert len(response.items) == 2
    assert response.items[0].name == "taco shells"
    assert response.items[0].quantity == 1
    assert response.items[0].unit == "pack"
    assert response.items[0].unit_price is None
    assert response.items[0].api_ingredient_id is None
    assert response.items[0].category == "bakery"
    assert response.items[0].confidence == 0.82
    assert response.items[1].name == "whole milk"
    assert response.clarifying_questions == ["What lunchbox snacks do you want?"]
    assert llm_router.feature == Feature.SHOPPING_LIST_DESCRIPTION
    assert llm_router.schema is ShoppingParseResponse


def test_parse_shopping_description_allows_vague_items() -> None:
    llm_router = _FakeLLMRouter(
        ShoppingParseResponse(
            items=[
                {
                    "name": "lunchbox snacks",
                    "quantity": 1,
                    "unit": "units",
                    "unit_price": None,
                    "category": "snacks",
                    "confidence": 0.55,
                }
            ],
            clarifying_questions=[],
        )
    )

    response = parse_shopping_description(
        ShoppingParseRequest(text="some lunchbox snacks"),
        llm_router=llm_router,
    )

    assert response.items[0].name == "lunchbox snacks"
    assert response.items[0].quantity == 1
    assert response.items[0].unit == "units"
    assert response.items[0].unit_price is None
    assert response.items[0].confidence == 0.55
