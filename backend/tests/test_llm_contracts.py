from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, ValidationError

from glean.llm import invoke_structured
from glean.receipts.schemas import ScanResponse
from glean.recipes.stored import RecipeLlmResponse
from glean.shopping.schemas import ShoppingParseResponse, ShoppingProposalItem
from glean.shopping.service import SHOPPING_PARSE_SYSTEM_PROMPT
from glean.suggestions.schemas import SuggestionResponse
from tests.integration.evals.judges.rubrics import JudgeScoreResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

STRUCTURED_LLM_RESPONSE_SCHEMAS: tuple[type[BaseModel], ...] = (
    ScanResponse,
    ShoppingParseResponse,
    RecipeLlmResponse,
    SuggestionResponse,
    JudgeScoreResponse,
)


def test_shopping_proposal_item_serialises_null_api_ingredient_id() -> None:
    item = ShoppingProposalItem(
        name="bananas",
        quantity=6,
        unit="units",
        unit_price=None,
        category="produce",
        confidence=0.93,
    )

    assert item.api_ingredient_id is None
    assert item.model_dump()["api_ingredient_id"] is None


def test_shopping_proposal_item_rejects_llm_supplied_api_ingredient_id() -> None:
    with pytest.raises(ValidationError):
        ShoppingProposalItem.model_validate(
            {
                "name": "bananas",
                "quantity": 6,
                "unit": "units",
                "unit_price": None,
                "api_ingredient_id": "ingredient:banana",
                "category": "produce",
                "confidence": 0.93,
            }
        )


def test_shopping_llm_contract_does_not_expose_api_ingredient_id() -> None:
    validation_schema = ShoppingProposalItem.model_json_schema(mode="validation")
    serialisation_schema = ShoppingProposalItem.model_json_schema(mode="serialization")
    tool_schema = convert_to_openai_tool(ShoppingParseResponse)
    item_properties = tool_schema["function"]["parameters"]["properties"]["items"]["items"]["properties"]

    assert "api_ingredient_id" not in validation_schema["properties"]
    assert serialisation_schema["properties"]["api_ingredient_id"]["readOnly"] is True
    assert "api_ingredient_id" not in item_properties
    assert "api_ingredient_id" not in SHOPPING_PARSE_SYSTEM_PROMPT


@pytest.mark.parametrize(
    "schema",
    STRUCTURED_LLM_RESPONSE_SCHEMAS,
    ids=lambda schema: schema.__name__,
)
def test_structured_llm_response_tool_schemas_are_self_describing(schema: type[BaseModel]) -> None:
    assert _missing_tool_descriptions(schema) == []


@pytest.mark.parametrize(
    "schema",
    STRUCTURED_LLM_RESPONSE_SCHEMAS,
    ids=lambda schema: schema.__name__,
)
def test_invoke_structured_rejects_unstructured_text_for_all_llm_response_schemas(
    schema: type[BaseModel],
) -> None:
    model = MagicMock()
    model.with_structured_output.return_value.invoke.return_value = "not structured output"

    with pytest.raises(ValidationError):
        invoke_structured(model, schema, ["message"])


def _missing_tool_descriptions(schema: type[BaseModel]) -> list[str]:
    tool_schema = convert_to_openai_tool(schema)
    function_schema = tool_schema["function"]
    missing: list[str] = []

    if not function_schema.get("description"):
        missing.append(schema.__name__)

    missing.extend(
        _missing_schema_descriptions(
            function_schema["parameters"],
            schema.__name__,
            require_object_description=False,
        )
    )
    return missing


def _missing_schema_descriptions(
    schema: Mapping[str, Any],
    path: str,
    *,
    require_object_description: bool,
) -> list[str]:
    missing: list[str] = []

    if require_object_description and schema.get("type") == "object" and not schema.get("description"):
        missing.append(path)

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                continue
            property_path = f"{path}.{name}"
            if not property_schema.get("description"):
                missing.append(property_path)
            missing.extend(
                _missing_schema_descriptions(
                    property_schema,
                    property_path,
                    require_object_description=True,
                )
            )

    items_schema = schema.get("items")
    if isinstance(items_schema, dict):
        missing.extend(
            _missing_schema_descriptions(
                items_schema,
                f"{path}[]",
                require_object_description=True,
            )
        )

    return missing
