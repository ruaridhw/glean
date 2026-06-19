from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from glean.recipe_api.client import _iso_to_mins
from glean.recipes.import_normalization import (
    clean_recipe_title,
    normalise_public_text,
    nutrition_values_from_mapping,
    sane_import_time_mins,
)
from glean.recipes.schemas import InstructionOut, NutritionOut, RecipeIngredientOut, RecipeOut

if TYPE_CHECKING:
    from glean.recipe_api.schemas import RecipeApiRecipe

__all__ = [
    "RecipeImportError",
    "RecipeLlmResponse",
    "RecipeParseResult",
    "RecipeProvenance",
    "StoredIngredient",
    "StoredInstruction",
    "StoredNutrition",
    "StoredRecipe",
    "stored_from_llm_json",
    "stored_from_llm_response",
    "stored_from_recipe_api",
    "stored_from_schema_org",
    "stored_to_recipe_out",
    "validate_importable_recipe",
]


class RecipeImportError(Exception):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        self.message = message
        super().__init__(message)


class StoredNutrition(BaseModel):
    """Nutrition fields as persisted in the server-side recipe corpus."""

    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


class StoredIngredient(BaseModel):
    """Ingredient fields as persisted before adapting to the public recipe response."""

    api_ingredient_id: str | None = None
    canonical_name: str
    quantity: float = 0
    unit: str = ""
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = Field(default_factory=list)


class StoredInstruction(BaseModel):
    """Instruction step fields as persisted in the server-side recipe corpus."""

    step_number: int
    phase: str
    text: str


class RecipeProvenance(BaseModel):
    source_url: str
    parser: str
    fetched_url: str | None = None
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)


class RecipeLlmResponse(BaseModel):
    """Structured response expected from the recipe extraction LLM."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str
    source_url: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    total_time: str | None = None
    prep_time: str | None = None
    active_time: str | None = None
    yield_: str | int | list[str | int] | None = Field(default=None, alias="yield")
    recipe_yield: str | int | list[str | int] | None = Field(default=None, alias="recipeYield")
    ingredients: list[str]
    instructions: list[str]
    dietary_flags: list[str] = Field(default_factory=list)
    not_suitable_for: list[str] = Field(default_factory=list)

    @field_validator("total_time", "prep_time", "active_time")
    @classmethod
    def _validate_iso_duration(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if _iso_to_mins(value) is None:
            raise ValueError("must be an ISO-8601 duration like PT30M")
        return value


class StoredRecipe(BaseModel):
    """Recipe record used by imports, offline jobs, and corpus cache.

    `StoredRecipe` is the internal persistence shape. It keeps parser metadata
    and source provenance for the import pipeline. Convert it to `RecipeOut` only
    at the API boundary.
    """

    external_id: str
    title: str
    source_url: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    active_time_mins: int | None = None
    total_time_mins: int | None = None
    dietary_flags: list[str] = Field(default_factory=list)
    not_suitable_for: list[str] = Field(default_factory=list)
    yield_count: int | None = None
    nutrition: StoredNutrition | None = None
    instructions: list[StoredInstruction] = Field(default_factory=list)
    ingredients: list[StoredIngredient] = Field(default_factory=list)
    provenance: RecipeProvenance | None = None


class RecipeParseResult(BaseModel):
    """Envelope returned by import parsers, including failure metadata when parsing fails."""

    recipe: StoredRecipe | None = None
    parser: str
    source_url: str
    fetched_url: str | None = None
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)
    failure_category: str | None = None


if TYPE_CHECKING:
    _vulture_pydantic_field_references = (
        RecipeProvenance.parser,
        RecipeProvenance.fetched_url,
        RecipeProvenance.warnings,
        StoredRecipe.provenance,
        RecipeParseResult.parser,
        RecipeParseResult.fetched_url,
        RecipeParseResult.warnings,
        RecipeParseResult.failure_category,
    )


def validate_importable_recipe(recipe: StoredRecipe) -> StoredRecipe:
    if not recipe.title.strip():
        raise RecipeImportError("missing_title", "Recipe title is required")
    if not recipe.ingredients:
        raise RecipeImportError("no_ingredients", "Recipe must include at least one ingredient")
    if len(recipe.instructions) < 2:
        raise RecipeImportError("too_few_instructions", "Recipe must include at least two instruction steps")
    return recipe


def stored_from_recipe_api(api_recipe: RecipeApiRecipe) -> StoredRecipe:
    nutrition_source = api_recipe.nutrition.per_serving

    return StoredRecipe(
        external_id=f"recipeapi:{api_recipe.id}",
        title=api_recipe.name,
        source_url=api_recipe.source_url,
        cuisine=api_recipe.cuisine,
        difficulty=api_recipe.difficulty,
        active_time_mins=_iso_to_mins(api_recipe.meta.active_time),
        total_time_mins=_iso_to_mins(api_recipe.meta.total_time),
        dietary_flags=api_recipe.dietary.flags,
        not_suitable_for=api_recipe.dietary.not_suitable_for,
        yield_count=api_recipe.meta.yield_count,
        nutrition=StoredNutrition(
            calories=nutrition_source.calories,
            protein_g=nutrition_source.protein_g,
            carbohydrates_g=nutrition_source.carbohydrates_g,
            fat_g=nutrition_source.fat_g,
            fibre_g=nutrition_source.fibre_g,
            sugar_g=nutrition_source.sugar_g,
            sodium_mg=nutrition_source.sodium_mg,
        ),
        instructions=[
            StoredInstruction(step_number=instruction.step_number, phase=instruction.phase, text=instruction.text)
            for instruction in api_recipe.instructions
        ],
        ingredients=[
            StoredIngredient(
                api_ingredient_id=f"recipeapi:{ingredient.ingredient_id}",
                canonical_name=ingredient.name,
                quantity=ingredient.quantity or 0.0,
                unit=ingredient.unit or "",
                preparation=ingredient.preparation,
                is_optional=ingredient.is_optional,
                substitutions=ingredient.substitutions,
            )
            for group in api_recipe.ingredients
            for ingredient in group.items
        ],
        provenance=RecipeProvenance(
            source_url=api_recipe.source_url or "",
            parser="recipeapi",
        ),
    )


def stored_from_schema_org(data: dict, *, source_url: str) -> StoredRecipe:
    raw_instructions = data.get("recipeInstructions", [])
    raw_ingredients = data.get("recipeIngredient", [])

    return validate_importable_recipe(
        StoredRecipe(
            external_id=_url_external_id(source_url),
            title=clean_recipe_title(data.get("name")),
            source_url=source_url,
            cuisine=_string_value(data.get("recipeCuisine")) or None,
            difficulty=None,
            active_time_mins=sane_import_time_mins(
                _iso_to_mins(_string_value(data.get("prepTime") or data.get("cookTime")))
            ),
            total_time_mins=sane_import_time_mins(_iso_to_mins(_string_value(data.get("totalTime")))),
            dietary_flags=[],
            not_suitable_for=[],
            yield_count=_parse_yield_count(data.get("recipeYield")),
            nutrition=_stored_nutrition_from_values(nutrition_values_from_mapping(data.get("nutrition"))),
            instructions=_instructions_from_schema_org(raw_instructions),
            ingredients=_ingredient_strings(raw_ingredients),
            provenance=RecipeProvenance(source_url=source_url, parser="schema.org"),
        )
    )


def stored_from_llm_json(data: dict, *, source_url: str) -> StoredRecipe:
    try:
        llm_response = RecipeLlmResponse.model_validate(data)
    except ValidationError as exc:
        raise RecipeImportError("invalid_llm_json", "Recipe extraction model returned malformed fields") from exc

    return stored_from_llm_response(llm_response, source_url=source_url)


def stored_from_llm_response(data: RecipeLlmResponse, *, source_url: str) -> StoredRecipe:
    recipe_source_url = _string_value(data.source_url) or source_url

    return validate_importable_recipe(
        StoredRecipe(
            external_id=_url_external_id(source_url),
            title=clean_recipe_title(data.title),
            source_url=recipe_source_url,
            cuisine=_string_value(data.cuisine) or None,
            difficulty=_string_value(data.difficulty) or None,
            active_time_mins=sane_import_time_mins(_iso_to_mins(data.prep_time or data.active_time)),
            total_time_mins=sane_import_time_mins(_iso_to_mins(data.total_time)),
            dietary_flags=_string_list(data.dietary_flags),
            not_suitable_for=_string_list(data.not_suitable_for),
            yield_count=_parse_yield_count(data.yield_ or data.recipe_yield),
            nutrition=None,
            instructions=_instruction_strings(data.instructions),
            ingredients=_ingredient_strings(data.ingredients),
            provenance=RecipeProvenance(source_url=source_url, parser="llm"),
        )
    )


def stored_to_recipe_out(recipe: StoredRecipe) -> RecipeOut:
    return RecipeOut(
        external_id=recipe.external_id,
        title=recipe.title,
        source_url=recipe.source_url,
        cuisine=recipe.cuisine,
        difficulty=recipe.difficulty,
        active_time_mins=recipe.active_time_mins,
        total_time_mins=recipe.total_time_mins,
        dietary_flags=recipe.dietary_flags,
        not_suitable_for=recipe.not_suitable_for,
        yield_count=recipe.yield_count,
        nutrition=_nutrition_out(recipe.nutrition),
        instructions=[
            InstructionOut(
                step_number=instruction.step_number,
                phase=instruction.phase,
                text=instruction.text,
            )
            for instruction in recipe.instructions
        ],
        ingredients=[
            RecipeIngredientOut(
                api_ingredient_id=ingredient.api_ingredient_id,
                canonical_name=ingredient.canonical_name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                preparation=ingredient.preparation,
                is_optional=ingredient.is_optional,
                substitutions=ingredient.substitutions,
            )
            for ingredient in recipe.ingredients
        ],
    )


def _url_external_id(source_url: str) -> str:
    return hashlib.sha256(source_url.encode()).hexdigest()[:16]


def _stored_nutrition_from_values(values: dict[str, float] | None) -> StoredNutrition | None:
    return StoredNutrition(**values) if values else None


def _nutrition_out(nutrition: StoredNutrition | None) -> NutritionOut | None:
    if nutrition is None:
        return None
    return NutritionOut(
        calories=nutrition.calories,
        protein_g=nutrition.protein_g,
        carbohydrates_g=nutrition.carbohydrates_g,
        fat_g=nutrition.fat_g,
        fibre_g=nutrition.fibre_g,
        sugar_g=nutrition.sugar_g,
        sodium_mg=nutrition.sodium_mg,
    )


def _parse_yield_count(raw_yield: Any) -> int | None:
    if raw_yield is None:
        return None
    if isinstance(raw_yield, list):
        raw_yield = raw_yield[0] if raw_yield else None
    match = re.search(r"\d+", str(raw_yield or ""))
    return int(match.group()) if match else None


def _ingredient_strings(raw_ingredients: Any) -> list[StoredIngredient]:
    # Local import avoids a cycle: the shared parser constructs StoredIngredient.
    from glean.recipes.ingredient_parser import parse_ingredient_text  # noqa: PLC0415

    if not isinstance(raw_ingredients, list):
        raw_ingredients = [raw_ingredients] if raw_ingredients else []

    ingredients: list[StoredIngredient] = []
    for ingredient in raw_ingredients:
        parsed = parse_ingredient_text(_string_value(ingredient))
        if parsed is not None:
            ingredients.append(parsed)
    return ingredients


def _instructions_from_schema_org(raw_instructions: Any) -> list[StoredInstruction]:
    if not isinstance(raw_instructions, list):
        raw_instructions = [raw_instructions] if raw_instructions else []

    instruction_texts: list[str] = []
    for instruction in raw_instructions:
        if isinstance(instruction, dict) and "itemListElement" in instruction:
            section_steps = instruction["itemListElement"]
            if isinstance(section_steps, list):
                instruction_texts.extend(_schema_instruction_text(step) for step in section_steps)
            else:
                instruction_texts.append(_schema_instruction_text(section_steps))
        else:
            instruction_texts.append(_schema_instruction_text(instruction))

    return _instruction_strings(instruction_texts)


def _schema_instruction_text(instruction: Any) -> str:
    if isinstance(instruction, dict):
        return _string_value(instruction.get("text") or instruction.get("name"))
    return _string_value(instruction)


def _instruction_strings(raw_instructions: Any) -> list[StoredInstruction]:
    if not isinstance(raw_instructions, list):
        raw_instructions = [raw_instructions] if raw_instructions else []

    return [
        StoredInstruction(step_number=index, phase="main", text=text)
        for index, text in enumerate((_string_value(instruction) for instruction in raw_instructions), start=1)
        if text
    ]


def _string_value(value: Any) -> str:
    return normalise_public_text(value)


def _string_list(values: list[str]) -> list[str]:
    return [text for value in values if (text := _string_value(value))]
