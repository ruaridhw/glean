from __future__ import annotations

from typing import TYPE_CHECKING

from glean.observability import logger
from glean.recipe_api.client import RecipeApiClient, _iso_to_mins
from glean.recipes import providers as recipe_providers
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.schemas import (
    ImportUrlRequest,
    RecipeOut,
    RecipeSearchResponse,
    RecipeSearchResult,
)
from glean.recipes.stored import RecipeImportError, stored_from_recipe_api, stored_to_recipe_out

# `stored_from_recipe_api` is the one recipe-api adapter and the one place the
# "recipeapi:{id}" id convention is defined. Corpus/import ids never carry this
# prefix, but recipe-api.com itself knows nothing about it, so any id we hand
# back to the upstream client must have it stripped first.
_RECIPE_API_ID_PREFIX = "recipeapi:"

if TYPE_CHECKING:
    from pydantic import SecretStr

    from glean.llm import LLMRouter


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
    if corpus_recipe is not None:
        return stored_to_recipe_out(corpus_recipe)

    upstream_id = recipe_id.removeprefix(_RECIPE_API_ID_PREFIX)
    client = RecipeApiClient(base_url=recipe_api_base_url, api_key=recipe_api_key.get_secret_value())
    api_recipe = client.get_recipe(upstream_id)
    return stored_to_recipe_out(stored_from_recipe_api(api_recipe))


def import_recipe_from_url(request: ImportUrlRequest, *, llm_router: LLMRouter) -> RecipeOut:
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
                llm_router=llm_router,
                fetched_url=request.fetched_url,
            )
        else:
            result = recipe_providers.import_url_to_canonical(request.url, llm_router=llm_router)
    except RecipeImportError as exc:
        raise ValueError(exc.message) from exc

    if result.recipe is None:
        raise ValueError(result.failure_category or "Recipe import failed")

    logger.info(
        "recipe import completed",
        extra={
            "url": request.url,
            "parser": result.parser,
        },
    )
    corpus_store.save(result.recipe)
    return stored_to_recipe_out(result.recipe)
