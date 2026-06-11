from __future__ import annotations

from typing import TYPE_CHECKING

from glean.observability import logger
from glean.recipe_api.client import RecipeApiClient, _iso_to_mins
from glean.recipes import providers as recipe_providers
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.schemas import (
    ImportUrlRequest,
    InstructionOut,
    NutritionOut,
    RecipeIngredientOut,
    RecipeOut,
    RecipeSearchResponse,
    RecipeSearchResult,
)
from glean.recipes.stored import RecipeImportError, stored_to_recipe_out

URL_PARSE_SYSTEM_PROMPT = recipe_providers.URL_PARSE_SYSTEM_PROMPT

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from pydantic import SecretStr

    from glean.recipe_api.schemas import RecipeApiRecipe


def _api_recipe_to_out(api_recipe: RecipeApiRecipe) -> RecipeOut:
    """Convert a recipe-api.com response to our internal RecipeOut shape."""
    nutrition_source = api_recipe.nutrition.per_serving
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
        for group in api_recipe.ingredients
        for ing in group.items
    ]
    nutrition = NutritionOut(
        calories=nutrition_source.calories,
        protein_g=nutrition_source.protein_g,
        carbohydrates_g=nutrition_source.carbohydrates_g,
        fat_g=nutrition_source.fat_g,
        fibre_g=nutrition_source.fibre_g,
        sugar_g=nutrition_source.sugar_g,
        sodium_mg=nutrition_source.sodium_mg,
    )
    return RecipeOut(
        external_id=api_recipe.id,
        title=api_recipe.name,
        source_url=api_recipe.source_url,
        cuisine=api_recipe.cuisine,
        difficulty=api_recipe.difficulty,
        active_time_mins=_iso_to_mins(api_recipe.meta.active_time),
        total_time_mins=_iso_to_mins(api_recipe.meta.total_time),
        dietary_flags=api_recipe.dietary.flags,
        not_suitable_for=api_recipe.dietary.not_suitable_for,
        yield_count=api_recipe.meta.yield_count,
        nutrition=nutrition,
        instructions=instructions,
        ingredients=ingredients,
    )


def search_recipes(
    *,
    recipe_api_base_url: str,
    recipe_api_key: SecretStr,
    q: str | None = None,
    cuisine: str | None = None,
    dietary: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> RecipeSearchResponse:
    corpus_results, corpus_total = RecipeCorpusStore().search(
        q=q,
        cuisine=cuisine,
        dietary=dietary,
        page=page,
        per_page=per_page,
    )
    if corpus_total > 0:
        return RecipeSearchResponse(
            results=[
                RecipeSearchResult(
                    external_id=stored_to_recipe_out(recipe).external_id,
                    title=recipe.title,
                    cuisine=recipe.cuisine,
                    difficulty=recipe.difficulty,
                    total_time_mins=recipe.total_time_mins,
                    dietary_flags=recipe.dietary_flags,
                )
                for recipe in corpus_results
            ],
            total=corpus_total,
        )

    client = RecipeApiClient(base_url=recipe_api_base_url, api_key=recipe_api_key.get_secret_value())
    api_response = client.search(q=q, cuisine=cuisine, dietary=dietary, page=page, per_page=per_page)
    results = [
        RecipeSearchResult(
            external_id=r.id,
            title=r.name,
            cuisine=r.cuisine,
            difficulty=r.difficulty,
            total_time_mins=_iso_to_mins(r.meta.total_time),
            dietary_flags=r.dietary.flags,
        )
        for r in api_response.data
    ]
    return RecipeSearchResponse(results=results, total=api_response.meta.total)


def get_recipe(recipe_id: str, *, recipe_api_base_url: str, recipe_api_key: SecretStr) -> RecipeOut:
    corpus_store = RecipeCorpusStore()
    corpus_recipe = corpus_store.get(recipe_id)
    if corpus_recipe is None and ":" not in recipe_id:
        corpus_recipe = corpus_store.get(f"recipeapi:{recipe_id}")
    if corpus_recipe is not None:
        return stored_to_recipe_out(corpus_recipe)

    client = RecipeApiClient(base_url=recipe_api_base_url, api_key=recipe_api_key.get_secret_value())
    api_recipe = client.get_recipe(recipe_id)
    return _api_recipe_to_out(api_recipe)


def import_recipe_from_url(request: ImportUrlRequest, *, model: BaseChatModel) -> RecipeOut:
    try:
        recipe_providers.validate_public_https_url(request.url)
    except RecipeImportError as exc:
        raise ValueError(exc.message) from exc

    corpus_store = RecipeCorpusStore()
    if corpus_recipe := corpus_store.get_by_source_url(request.url):
        return stored_to_recipe_out(corpus_recipe)

    try:
        if request.rendered_html is not None:
            result = recipe_providers.import_html_to_canonical(
                request.url,
                request.rendered_html,
                model=model,
                fetched_url=request.fetched_url,
            )
        else:
            result = recipe_providers.import_url_to_canonical(request.url, model=model)
    except RecipeImportError as exc:
        raise ValueError(exc.message) from exc

    if result.recipe is None:
        raise ValueError(result.failure_category or "Recipe import failed")

    logger.info(
        "recipe import completed",
        extra={
            "url": request.url,
            "provider": result.provider,
            "parser": result.parser,
        },
    )
    corpus_store.save(result.recipe)
    return stored_to_recipe_out(result.recipe)
