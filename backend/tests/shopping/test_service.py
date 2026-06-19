from __future__ import annotations

from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse
from glean.shopping.service import parse_shopping_description


class _StructuredInvoker:
    def __init__(self, parent: _FakeModel, response: ShoppingParseResponse) -> None:
        self.parent = parent
        self.response = response

    def invoke(self, messages: list[object], config: dict | None = None) -> ShoppingParseResponse:
        self.parent.messages = messages
        self.parent.config = config
        return self.response


class _FakeModel:
    def __init__(self, response: ShoppingParseResponse) -> None:
        self.response = response
        self.messages: list[object] = []
        self.config: dict | None = None
        self.schema: type[object] | None = None

    def with_structured_output(self, schema: type[object]) -> _StructuredInvoker:
        self.schema = schema
        return _StructuredInvoker(self, self.response)


def test_parse_shopping_description_returns_proposed_items() -> None:
    model = _FakeModel(
        ShoppingParseResponse(
            items=[
                {
                    "name": "taco shells",
                    "quantity": 1,
                    "unit": "pack",
                    "unit_price": None,
                    "api_ingredient_id": "taco-shells",
                    "category": "bakery",
                    "confidence": 0.82,
                },
                {
                    "name": "whole milk",
                    "quantity": 1,
                    "unit": "bottle",
                    "unit_price": None,
                    "api_ingredient_id": None,
                    "category": "dairy",
                    "confidence": 0.91,
                },
            ],
            clarifying_questions=["What lunchbox snacks do you want?"],
        )
    )

    response = parse_shopping_description(
        ShoppingParseRequest(text="stuff for tacos, milk, and lunchbox snacks"),
        model=model,
    )

    assert len(response.items) == 2
    assert response.items[0].name == "taco shells"
    assert response.items[0].quantity == 1
    assert response.items[0].unit == "pack"
    assert response.items[0].unit_price is None
    assert response.items[0].api_ingredient_id == "taco-shells"
    assert response.items[0].category == "bakery"
    assert response.items[0].confidence == 0.82
    assert response.items[1].name == "whole milk"
    assert response.clarifying_questions == ["What lunchbox snacks do you want?"]
    assert model.config == {"metadata": {"feature": "shopping-list-description"}}
    assert model.schema is ShoppingParseResponse


def test_parse_shopping_description_allows_vague_items() -> None:
    model = _FakeModel(
        ShoppingParseResponse(
            items=[
                {
                    "name": "lunchbox snacks",
                    "quantity": 1,
                    "unit": "units",
                    "unit_price": None,
                    "api_ingredient_id": None,
                    "category": "snacks",
                    "confidence": 0.55,
                }
            ],
            clarifying_questions=[],
        )
    )

    response = parse_shopping_description(
        ShoppingParseRequest(text="some lunchbox snacks"),
        model=model,
    )

    assert response.items[0].name == "lunchbox snacks"
    assert response.items[0].quantity == 1
    assert response.items[0].unit == "units"
    assert response.items[0].unit_price is None
    assert response.items[0].confidence == 0.55
