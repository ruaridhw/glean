from __future__ import annotations

from glean.llm import Feature
from glean.receipts.schemas import INGREDIENT_CATEGORY_FOOD_GROUPS
from glean.shopping.schemas import ShoppingParseRequest, ShoppingParseResponse, ShoppingUnit
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
                    "category": "grains",
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
    assert response.items[0].category == "grains"
    assert response.items[0].food_group == "carbohydrates"
    assert response.items[0].confidence == 0.82
    assert response.items[1].name == "whole milk"
    assert response.items[1].category == "dairy"
    assert response.items[1].food_group == "dairy"
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
                    "category": None,
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
    assert response.items[0].category is None
    assert response.items[0].food_group == "other"
    assert response.items[0].confidence == 0.55


def test_parse_shopping_description_rejects_out_of_taxonomy_category() -> None:
    """A category the LLM invents outside the fixed taxonomy is coerced to null, not passed
    through, and food_group still resolves to "other" rather than null."""
    llm_router = _FakeLLMRouter(
        ShoppingParseResponse(
            items=[
                {
                    "name": "lunchbox snacks",
                    "quantity": 1,
                    "unit": "units",
                    "unit_price": None,
                    "category": "snacks",  # not in the taxonomy
                    "confidence": 0.55,
                }
            ],
        )
    )

    response = parse_shopping_description(
        ShoppingParseRequest(text="some lunchbox snacks"),
        llm_router=llm_router,
    )

    assert response.items[0].category is None
    assert response.items[0].food_group == "other"


def test_prompt_states_intent_and_ambiguity_policy_not_schema_rules() -> None:
    llm_router = _FakeLLMRouter(ShoppingParseResponse(items=[]))
    parse_shopping_description(ShoppingParseRequest(text="tacos"), llm_router=llm_router)
    system_prompt = llm_router.messages[0].content

    assert not [unit for unit in ShoppingUnit if f'"{unit}"' in system_prompt]
    assert not [category for category in INGREDIENT_CATEGORY_FOOD_GROUPS if category in system_prompt]
    assert "unit_price" not in system_prompt
    assert "api_ingredient_id" not in system_prompt
    assert "confidence of 0.6 or lower" in system_prompt
