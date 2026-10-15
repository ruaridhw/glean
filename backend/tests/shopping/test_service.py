from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glean.llm import Feature
from glean.receipts.schemas import INGREDIENT_CATEGORY_FOOD_GROUPS
from glean.shopping.schemas import ShoppingBatchParseResponse, ShoppingParseRequest, ShoppingParseResponse, ShoppingUnit
from glean.shopping.service import (
    BATCH_PARSE_SYSTEM_PROMPT,
    SHOPPING_PARSE_SYSTEM_PROMPT,
    parse_shopping_description,
)

if TYPE_CHECKING:
    from glean.decisions import DecisionClient
    from glean.recipe_api.blob_store import BlobStore


class _FakeLLMRouter:
    def __init__(self, response: ShoppingParseResponse) -> None:
        self.response = response
        self.feature: Feature | None = None
        self.schema: type[object] | None = None
        self.messages: list[object] = []

    def model_id_for(self, feature: Feature) -> str:
        return "test/model"

    def invoke(self, feature: Feature, schema: type[object], messages: list[object], **_: object) -> object:
        self.feature = feature
        self.schema = schema
        self.messages = messages
        return ShoppingBatchParseResponse.model_validate(
            {
                "units": [
                    {
                        "number": 1,
                        **self.response.model_dump(exclude={"items": {"__all__": {"food_group", "api_ingredient_id"}}}),
                    }
                ]
            }
        )


def test_parse_shopping_description_returns_proposed_items(
    decision_client: DecisionClient, parse_cache: BlobStore
) -> None:
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
        ShoppingParseRequest(text="stuff for tacos"),
        llm_router=llm_router,
        decision_client=decision_client,
        cache=parse_cache,
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
    assert llm_router.schema is ShoppingBatchParseResponse


def test_parse_shopping_description_allows_vague_items(decision_client: DecisionClient, parse_cache: BlobStore) -> None:
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
        decision_client=decision_client,
        cache=parse_cache,
    )

    assert response.items[0].name == "lunchbox snacks"
    assert response.items[0].quantity == 1
    assert response.items[0].unit == "units"
    assert response.items[0].unit_price is None
    assert response.items[0].category is None
    assert response.items[0].food_group == "other"
    assert response.items[0].confidence == 0.55


def test_parse_shopping_description_rejects_out_of_taxonomy_category(
    decision_client: DecisionClient, parse_cache: BlobStore
) -> None:
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
        decision_client=decision_client,
        cache=parse_cache,
    )

    assert response.items[0].category is None
    assert response.items[0].food_group == "other"


@pytest.mark.parametrize("system_prompt", [SHOPPING_PARSE_SYSTEM_PROMPT, BATCH_PARSE_SYSTEM_PROMPT], ids=str)
def test_prompts_state_intent_and_ambiguity_policy_not_schema_rules(system_prompt: str) -> None:
    assert not [unit for unit in ShoppingUnit if f'"{unit}"' in system_prompt]
    assert not [category for category in INGREDIENT_CATEGORY_FOOD_GROUPS if category in system_prompt]
    assert "unit_price" not in system_prompt
    assert "api_ingredient_id" not in system_prompt


@pytest.mark.parametrize("system_prompt", [SHOPPING_PARSE_SYSTEM_PROMPT, BATCH_PARSE_SYSTEM_PROMPT], ids=str)
def test_prompts_that_expand_dishes_cap_the_confidence_of_the_guessed_ingredients(system_prompt: str) -> None:
    assert "confidence of 0.6 or lower" in system_prompt
