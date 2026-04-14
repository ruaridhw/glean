from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage

from glean.llm import Feature
from glean.observability import logger
from glean.recipe_api.client import RecipeApiClient, _iso_to_mins
from glean.recipes.schemas import (
    ImportUrlRequest,
    InstructionOut,
    NutritionOut,
    RecipeIngredientOut,
    RecipeOut,
    RecipeSearchResponse,
    RecipeSearchResult,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from glean.recipe_api.schemas import RecipeApiRecipe

URL_PARSE_SYSTEM_PROMPT = """You are a recipe extraction assistant. Given HTML from a recipe page,
extract the recipe details and return ONLY valid JSON with this exact structure (no markdown, no commentary):
{
  "title": "Recipe Name",
  "source_url": "https://...",
  "cuisine": null,
  "difficulty": null,
  "total_time": "PT30M",
  "prep_time": "PT10M",
  "yield": "4 servings",
  "ingredients": ["200g pasta", "2 eggs"],
  "instructions": ["Step 1 text", "Step 2 text"],
  "dietary_flags": [],
  "not_suitable_for": []
}
Return null values for fields that cannot be determined. Return ONLY the JSON object."""


def _validate_url_ssrf(url: str) -> None:
    """Reject non-HTTPS URLs and those resolving to private/loopback/link-local IPs."""
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are allowed")

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: no hostname")

    try:
        resolved_ip = socket.gethostbyname(hostname)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from exc

    try:
        addr = ipaddress.ip_address(resolved_ip)
    except ValueError as exc:
        raise ValueError(f"Invalid IP address resolved: {resolved_ip}") from exc

    if addr.is_private or addr.is_loopback or addr.is_link_local:
        raise ValueError(f"URL resolves to a disallowed IP address: {resolved_ip}")


def _parse_schema_org(html: str) -> dict | None:
    """Parse <script type='application/ld+json'> blocks and find @type == 'Recipe'."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle both single objects and @graph arrays
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict) and "@graph" in data:
            candidates = data["@graph"]
        else:
            candidates = [data]

        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "Recipe":
                return item

    return None


def _parse_yield_count(yield_str: str | None) -> int | None:
    """Extract numeric yield from strings like '4 servings' or '2'."""
    if not yield_str:
        return None
    match = re.search(r"\d+", str(yield_str))
    return int(match.group()) if match else None


def _schema_org_to_recipe_out(data: dict, url: str) -> RecipeOut:
    """Convert a schema.org Recipe dict to our RecipeOut shape."""
    raw_instructions = data.get("recipeInstructions", [])
    instructions: list[InstructionOut] = []
    for i, step in enumerate(raw_instructions, start=1):
        if isinstance(step, str):
            text = step
        elif isinstance(step, dict):
            text = step.get("text", "")
        else:
            text = str(step)
        instructions.append(InstructionOut(step_number=i, phase="main", text=text))

    raw_ingredients = data.get("recipeIngredient", [])
    ingredients: list[RecipeIngredientOut] = [
        RecipeIngredientOut(
            api_ingredient_id=f"schema-{i}",
            canonical_name=ing,
            quantity=0.0,
            unit="",
        )
        for i, ing in enumerate(raw_ingredients, start=1)
    ]

    total_time_mins = _iso_to_mins(data.get("totalTime"))
    active_time_mins = _iso_to_mins(data.get("prepTime") or data.get("cookTime"))
    yield_count = _parse_yield_count(data.get("recipeYield"))

    return RecipeOut(
        external_id=url,
        title=data.get("name", ""),
        source_url=url,
        cuisine=data.get("recipeCuisine"),
        difficulty=None,
        active_time_mins=active_time_mins,
        total_time_mins=total_time_mins,
        dietary_flags=[],
        not_suitable_for=[],
        yield_count=yield_count,
        nutrition=NutritionOut(),
        instructions=instructions,
        ingredients=ingredients,
    )


def _api_recipe_to_out(api_recipe: RecipeApiRecipe) -> RecipeOut:
    """Convert a recipe-api.com response to our internal RecipeOut shape."""
    instructions = [
        InstructionOut(step_number=instr.step_number, phase=instr.phase, text=instr.text)
        for instr in api_recipe.instructions
    ]
    ingredients = [
        RecipeIngredientOut(
            api_ingredient_id=ing.ingredient_id,
            canonical_name=ing.name,
            quantity=ing.quantity or 0.0,
            unit=ing.unit or "",
            preparation=ing.preparation,
            is_optional=ing.is_optional,
            substitutions=ing.substitutions,
        )
        for ing in api_recipe.ingredients
    ]
    nutrition = NutritionOut(
        calories=api_recipe.nutrition.calories,
        protein_g=api_recipe.nutrition.protein_g,
        carbohydrates_g=api_recipe.nutrition.carbohydrates_g,
        fat_g=api_recipe.nutrition.fat_g,
        fibre_g=api_recipe.nutrition.fibre_g,
        sugar_g=api_recipe.nutrition.sugar_g,
        sodium_mg=api_recipe.nutrition.sodium_mg,
    )
    return RecipeOut(
        external_id=api_recipe.id,
        title=api_recipe.name,
        source_url=api_recipe.source_url,
        cuisine=api_recipe.cuisine,
        difficulty=api_recipe.difficulty,
        active_time_mins=_iso_to_mins(api_recipe.meta.active_time),
        total_time_mins=_iso_to_mins(api_recipe.meta.total_time),
        dietary_flags=api_recipe.flags,
        not_suitable_for=api_recipe.not_suitable_for,
        yield_count=api_recipe.meta.yield_count,
        nutrition=nutrition,
        instructions=instructions,
        ingredients=ingredients,
    )


def search_recipes(
    *,
    recipe_api_base_url: str,
    recipe_api_key: str,
    q: str | None = None,
    cuisine: str | None = None,
    dietary: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> RecipeSearchResponse:
    client = RecipeApiClient(base_url=recipe_api_base_url, api_key=recipe_api_key)
    api_response = client.search(q=q, cuisine=cuisine, dietary=dietary, page=page, per_page=per_page)
    results = [
        RecipeSearchResult(
            external_id=r.id,
            title=r.name,
            cuisine=r.cuisine,
            difficulty=r.difficulty,
            total_time_mins=_iso_to_mins(r.total_time),
            dietary_flags=r.flags,
        )
        for r in api_response.results
    ]
    return RecipeSearchResponse(results=results, total=api_response.total)


def get_recipe(recipe_id: str, *, recipe_api_base_url: str, recipe_api_key: str) -> RecipeOut:
    client = RecipeApiClient(base_url=recipe_api_base_url, api_key=recipe_api_key)
    api_recipe = client.get_recipe(recipe_id)
    return _api_recipe_to_out(api_recipe)


def _llm_json_to_recipe_out(data: dict, url: str) -> RecipeOut:
    """Convert LLM-extracted JSON to RecipeOut."""
    raw_instructions = data.get("instructions", [])
    instructions = [
        InstructionOut(step_number=i, phase="main", text=step) for i, step in enumerate(raw_instructions, start=1)
    ]
    raw_ingredients = data.get("ingredients", [])
    ingredients = [
        RecipeIngredientOut(
            api_ingredient_id=f"llm-{i}",
            canonical_name=ing,
            quantity=0.0,
            unit="",
        )
        for i, ing in enumerate(raw_ingredients, start=1)
    ]
    total_time_mins = _iso_to_mins(data.get("total_time"))
    active_time_mins = _iso_to_mins(data.get("prep_time"))
    yield_count = _parse_yield_count(data.get("yield"))

    return RecipeOut(
        external_id=url,
        title=data.get("title", ""),
        source_url=data.get("source_url") or url,
        cuisine=data.get("cuisine"),
        difficulty=data.get("difficulty"),
        active_time_mins=active_time_mins,
        total_time_mins=total_time_mins,
        dietary_flags=data.get("dietary_flags", []),
        not_suitable_for=data.get("not_suitable_for", []),
        yield_count=yield_count,
        nutrition=NutritionOut(),
        instructions=instructions,
        ingredients=ingredients,
    )


def import_recipe_from_url(request: ImportUrlRequest, *, model: BaseChatModel) -> RecipeOut:
    _validate_url_ssrf(request.url)

    html = httpx.get(request.url, follow_redirects=True, timeout=10.0).text

    schema_data = _parse_schema_org(html)
    if schema_data and schema_data.get("recipeIngredient"):
        logger.info("recipe import via schema.org", extra={"url": request.url})
        return _schema_org_to_recipe_out(schema_data, request.url)

    logger.info("recipe import via LangChain/Claude fallback", extra={"url": request.url})
    llm = model
    response = llm.invoke(
        [
            SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this HTML:\n\n{html[:8000]}"),
        ],
        config={"metadata": {"feature": Feature.RECIPE_IMPORT}},
    )
    data = json.loads(response.content)
    return _llm_json_to_recipe_out(data, request.url)
