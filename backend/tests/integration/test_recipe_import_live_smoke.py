from __future__ import annotations

import json
from typing import Any

import pytest

from glean.recipes import providers
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.providers import FetchedPage, import_url_to_canonical
from glean.recipes.stored import RecipeParseResult, StoredRecipe

pytestmark = pytest.mark.integration

WEB_RECIPE_URLS = (
    "https://recipes.example.test/recipes/coconut-lentil-curry",
    "https://recipes.example.test/recipes/green-noodle-bowl",
)


def test_direct_url_import_parses_neutral_recipe_fixtures_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _NoLlm()
    pages = {
        WEB_RECIPE_URLS[0]: _schema_org_html(
            name="Coconut Lentil Curry",
            ingredients=["200g red lentils", "400ml coconut milk", "2 tsp curry powder"],
            instructions=["Rinse the lentils.", "Simmer everything together.", "Serve with rice."],
        ),
        WEB_RECIPE_URLS[1]: _schema_org_html(
            name="Green Noodle Bowl",
            ingredients=["180g noodles", "150g broccoli", "1 tbsp sesame oil"],
            instructions=["Cook the noodles.", "Steam the broccoli.", "Toss with sesame oil."],
        ),
    }

    def fetch_fixture(url: str, **_: Any) -> FetchedPage:
        return FetchedPage(url=url, text=pages[url])

    monkeypatch.setattr(providers, "fetch_public_https", fetch_fixture)

    results = [import_url_to_canonical(url, model=model) for url in WEB_RECIPE_URLS]

    recipes = [
        _assert_imported_recipe(
            result,
            title_contains=title,
            min_ingredients=3,
            min_instructions=3,
        )
        for result, title in zip(results, ("Coconut Lentil Curry", "Green Noodle Bowl"), strict=True)
    ]
    assert [recipe.source_url for recipe in recipes] == list(WEB_RECIPE_URLS)
    assert model.calls == 0


def test_direct_url_import_saves_neutral_recipe_fixtures(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    model = _NoLlm()
    corpus = RecipeCorpusStore(root=tmp_path / "corpus")
    html = _schema_org_html(
        name="Crispy Bean Tacos",
        ingredients=["400g black beans", "8 tortillas", "1 lime"],
        instructions=["Warm the beans.", "Toast the tortillas.", "Finish with lime."],
    )

    monkeypatch.setattr(providers, "fetch_public_https", lambda url, **_: FetchedPage(url=url, text=html))

    result = import_url_to_canonical(WEB_RECIPE_URLS[0], model=model)
    recipe = _assert_imported_recipe(
        result,
        title_contains="Crispy Bean Tacos",
        min_ingredients=3,
        min_instructions=3,
    )
    saved = corpus.save(recipe)
    loaded = corpus.get(saved.external_id)

    assert loaded is not None
    assert isinstance(loaded, StoredRecipe)
    assert loaded.title == "Crispy Bean Tacos"
    assert model.calls == 0


class _NoLlm:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *_: Any, **__: Any) -> None:
        self.calls += 1
        pytest.fail("Recipe smoke should parse structured data without invoking the LLM")


def _assert_imported_recipe(
    result: RecipeParseResult,
    *,
    title_contains: str,
    min_ingredients: int,
    min_instructions: int,
) -> StoredRecipe:
    assert result.recipe is not None
    assert result.parser == "schema.org"
    recipe = result.recipe
    assert isinstance(recipe, StoredRecipe)
    assert title_contains in recipe.title
    assert recipe.provenance is not None
    assert recipe.provenance.parser == "schema.org"
    assert len(recipe.ingredients) >= min_ingredients
    assert len(recipe.instructions) >= min_instructions
    return recipe


def _schema_org_html(*, name: str, ingredients: list[str], instructions: list[str]) -> str:
    instruction_json = [{"@type": "HowToStep", "text": instruction} for instruction in instructions]
    data = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": name,
        "totalTime": "PT30M",
        "recipeYield": "2",
        "recipeIngredient": ingredients,
        "recipeInstructions": instruction_json,
    }
    return f"""
    <html>
      <head>
        <script type="application/ld+json">
        {json.dumps(data)}
        </script>
      </head>
      <body><h1>{name}</h1></body>
    </html>
    """
