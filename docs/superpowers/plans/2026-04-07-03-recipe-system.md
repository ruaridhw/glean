# Recipe System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate recipe-api.com for browsing and searching recipes, import recipes by URL via Claude parsing, cache all fetched recipes in SQLite, and display recipe list and detail screens.

**Architecture:** The FastAPI backend acts as the only caller of recipe-api.com (keeping the API key server-side). Fetched recipe details are cached in SQLite on first fetch — the mobile app never calls recipe-api.com directly. Recipe ingredient names are resolved against the local `ingredients` table via `api_ingredient_id` UUID matching, falling back to Claude-normalised name creation.

**Tech Stack:** expo-sqlite, FastAPI, httpx (recipe API client), anthropic SDK, Pydantic v2, pytest, Jest + React Native Testing Library

**Depends on:** Plan 1 (Foundation), Plan 2 (Pantry) — `ingredients` table, `resolveOrCreateIngredient`, types, API client.

---

## File Structure

```
mobile/
  app/(tabs)/meals/
    index.tsx                  # Saved recipes list + Suggestions tab
    search.tsx                 # External recipe search screen
    [id].tsx                   # Recipe detail screen
  src/db/
    recipes.ts                 # SQLite recipe CRUD + ingredient joins

backend/
  src/glean/
    recipe_api/
      client.py                # httpx wrapper for recipe-api.com
      schemas.py               # Pydantic models matching recipe-api.com response
    recipes/
      router.py                # GET /recipes/search, GET /recipes/{id}, POST /recipes/import-url
      service.py               # Orchestration: fetch → parse → return
      schemas.py               # RecipeResponse (our internal shape)
  tests/
    recipes/
      test_router.py
      fixtures/
        recipe_detail.json     # Mocked recipe-api.com response for one recipe
        recipe_search.json     # Mocked recipe-api.com search results
        recipe_url_claude.json # Mocked Claude URL parse response
```

---

### Task 1: Recipe API client (backend)

**Files:**
- Create: `backend/src/glean/recipe_api/schemas.py`
- Create: `backend/src/glean/recipe_api/client.py`

- [ ] **Step 1: Write recipe_api/schemas.py**

```python
# backend/src/glean/recipe_api/schemas.py
from pydantic import BaseModel


class RecipeApiIngredient(BaseModel):
    ingredient_id: str   # UUID from recipe-api.com master DB
    name: str
    quantity: float | None = None
    unit: str | None = None
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class RecipeApiNutrition(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


class RecipeApiInstruction(BaseModel):
    step_number: int
    phase: str
    text: str


class RecipeApiMeta(BaseModel):
    total_time: str | None = None   # ISO 8601 e.g. "PT45M"
    active_time: str | None = None
    yield_count: int | None = None


class RecipeApiRecipe(BaseModel):
    id: str  # UUID
    name: str
    description: str | None = None
    category: str | None = None
    cuisine: str | None = None
    difficulty: str | None = None
    flags: list[str] = []
    not_suitable_for: list[str] = []
    meta: RecipeApiMeta = RecipeApiMeta()
    ingredients: list[RecipeApiIngredient] = []
    instructions: list[RecipeApiInstruction] = []
    nutrition: RecipeApiNutrition = RecipeApiNutrition()
    source_url: str | None = None


class RecipeApiSearchResult(BaseModel):
    id: str
    name: str
    cuisine: str | None = None
    difficulty: str | None = None
    total_time: str | None = None
    flags: list[str] = []


class RecipeApiSearchResponse(BaseModel):
    results: list[RecipeApiSearchResult]
    total: int
```

- [ ] **Step 2: Write recipe_api/client.py**

```python
# backend/src/glean/recipe_api/client.py
import re
import httpx
from glean.config import settings
from glean.observability import logger, tracer
from glean.recipe_api.schemas import RecipeApiRecipe, RecipeApiSearchResponse


def _iso_to_mins(iso: str | None) -> int | None:
    if not iso:
        return None
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


class RecipeApiClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.recipe_api_base_url,
            headers={"X-API-Key": settings.recipe_api_key},
            timeout=10.0,
        )

    @tracer.capture_method
    def search(
        self,
        q: str | None = None,
        cuisine: str | None = None,
        dietary: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> RecipeApiSearchResponse:
        params = {k: v for k, v in {
            "q": q, "cuisine": cuisine, "dietary": dietary,
            "page": page, "per_page": per_page,
        }.items() if v is not None}
        logger.info("recipe api search", extra={"params": params})
        resp = self._client.get("/recipes", params=params)
        resp.raise_for_status()
        return RecipeApiSearchResponse(**resp.json())

    @tracer.capture_method
    def get_recipe(self, recipe_id: str) -> RecipeApiRecipe:
        logger.info("recipe api fetch", extra={"id": recipe_id})
        resp = self._client.get(f"/recipes/{recipe_id}")
        resp.raise_for_status()
        return RecipeApiRecipe(**resp.json())

    def active_time_mins(self, recipe: RecipeApiRecipe) -> int | None:
        return _iso_to_mins(recipe.meta.active_time)

    def total_time_mins(self, recipe: RecipeApiRecipe) -> int | None:
        return _iso_to_mins(recipe.meta.total_time)


recipe_api_client = RecipeApiClient()
```

- [ ] **Step 3: Write test for _iso_to_mins**

```python
# backend/tests/recipes/test_client.py
from glean.recipe_api.client import _iso_to_mins


def test_iso_to_mins_hours_and_minutes() -> None:
    assert _iso_to_mins("PT1H30M") == 90


def test_iso_to_mins_minutes_only() -> None:
    assert _iso_to_mins("PT45M") == 45


def test_iso_to_mins_none_returns_none() -> None:
    assert _iso_to_mins(None) is None


def test_iso_to_mins_invalid_returns_none() -> None:
    assert _iso_to_mins("not-a-duration") is None
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/recipes/test_client.py -v
```
Expected: 4 passing

- [ ] **Step 5: Commit**

```bash
git add backend/src/glean/recipe_api/ backend/tests/recipes/test_client.py
git commit -m "🔗 recipe-api: typed httpx client with ISO duration parsing"
```

---

### Task 2: Backend recipes router (search + fetch + import by URL)

**Files:**
- Create: `backend/src/glean/recipes/schemas.py`
- Create: `backend/src/glean/recipes/service.py`
- Create: `backend/src/glean/recipes/router.py`
- Create: `backend/tests/recipes/test_router.py`
- Create: `backend/tests/recipes/fixtures/recipe_detail.json`
- Create: `backend/tests/recipes/fixtures/recipe_search.json`

- [ ] **Step 1: Write recipes/schemas.py**

```python
# backend/src/glean/recipes/schemas.py
from pydantic import BaseModel


class RecipeIngredientOut(BaseModel):
    api_ingredient_id: str
    canonical_name: str
    quantity: float
    unit: str
    preparation: str | None = None
    is_optional: bool = False
    substitutions: list[str] = []


class NutritionOut(BaseModel):
    calories: float
    protein_g: float
    carbohydrates_g: float
    fat_g: float
    fiber_g: float
    sugar_g: float
    sodium_mg: float


class InstructionOut(BaseModel):
    step_number: int
    phase: str
    text: str


class RecipeOut(BaseModel):
    external_id: str
    title: str
    source_url: str | None
    cuisine: str | None
    difficulty: str | None
    active_time_mins: int | None
    total_time_mins: int | None
    dietary_flags: list[str]
    not_suitable_for: list[str]
    yield_count: int | None
    nutrition: NutritionOut
    instructions: list[InstructionOut]
    ingredients: list[RecipeIngredientOut]


class RecipeSearchResult(BaseModel):
    external_id: str
    title: str
    cuisine: str | None
    difficulty: str | None
    total_time_mins: int | None
    dietary_flags: list[str]


class RecipeSearchResponse(BaseModel):
    results: list[RecipeSearchResult]
    total: int


class ImportUrlRequest(BaseModel):
    url: str
```

- [ ] **Step 2: Write test fixtures**

```json
// backend/tests/recipes/fixtures/recipe_search.json
{
  "results": [
    {"id": "abc-123", "name": "Spaghetti Carbonara", "cuisine": "Italian", "difficulty": "Easy", "total_time": "PT20M", "flags": []},
    {"id": "def-456", "name": "Chicken Tikka Masala", "cuisine": "Indian", "difficulty": "Intermediate", "total_time": "PT45M", "flags": ["Gluten-Free"]}
  ],
  "total": 2
}
```

```json
// backend/tests/recipes/fixtures/recipe_detail.json
{
  "id": "abc-123",
  "name": "Spaghetti Carbonara",
  "cuisine": "Italian",
  "difficulty": "Easy",
  "flags": [],
  "not_suitable_for": [],
  "meta": {"total_time": "PT20M", "active_time": "PT15M", "yield_count": 2},
  "ingredients": [
    {"ingredient_id": "uuid-spaghetti", "name": "spaghetti", "quantity": 200, "unit": "g", "preparation": null, "is_optional": false, "substitutions": []},
    {"ingredient_id": "uuid-eggs", "name": "eggs", "quantity": 3, "unit": "units", "preparation": "beaten", "is_optional": false, "substitutions": []}
  ],
  "instructions": [
    {"step_number": 1, "phase": "cook", "text": "Boil spaghetti in salted water until al dente."},
    {"step_number": 2, "phase": "cook", "text": "Mix eggs with cheese. Combine with pasta off the heat."}
  ],
  "nutrition": {"calories": 520, "protein_g": 24, "carbohydrates_g": 68, "fat_g": 16, "fiber_g": 3, "sugar_g": 2, "sodium_mg": 420}
}
```

- [ ] **Step 3: Install beautifulsoup4 and write recipes/service.py**

```bash
cd backend && uv add beautifulsoup4
```

```python
# backend/src/glean/recipes/service.py
import ipaddress
import json
import socket
from urllib.parse import urlparse

import anthropic
import httpx
from bs4 import BeautifulSoup

from glean.config import settings
from glean.observability import logger, tracer
from glean.recipe_api.client import recipe_api_client, _iso_to_mins
from glean.recipe_api.schemas import RecipeApiRecipe
from glean.recipes.schemas import (
    RecipeOut, RecipeSearchResponse, RecipeSearchResult,
    RecipeIngredientOut, NutritionOut, InstructionOut, ImportUrlRequest,
)

URL_PARSE_SYSTEM_PROMPT = """You are a recipe parser. Given the HTML content of a recipe webpage, extract:
- title: recipe name
- cuisine: cuisine type if identifiable
- difficulty: Easy/Intermediate/Advanced (estimate)
- active_time_mins: active cooking time in minutes
- total_time_mins: total time in minutes
- yield_count: number of servings
- dietary_flags: array of applicable flags from: Vegetarian, Vegan, Gluten-Free, Dairy-Free, Nut-Free
- not_suitable_for: array of allergens
- ingredients: array of {name, quantity, unit, preparation, is_optional, substitutions}
- instructions: array of {step_number, phase, text} where phase is prep/cook/assemble/finish
- nutrition: {calories, protein_g, carbohydrates_g, fat_g, fiber_g, sugar_g, sodium_mg} (estimate if not present)

Respond with ONLY valid JSON. No markdown."""


def _validate_url_ssrf(url: str) -> None:
    """Rejects non-HTTPS URLs and RFC 1918 / link-local resolved IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are supported")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: no hostname")
    try:
        resolved_ip = socket.gethostbyname(hostname)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from exc
    ip = ipaddress.ip_address(resolved_ip)
    if ip.is_private or ip.is_link_local or ip.is_loopback:
        raise ValueError(f"Resolved IP {resolved_ip} is not routable")


def _parse_schema_org(html: str) -> dict | None:
    """Extract schema.org/Recipe from <script type='application/ld+json'>. Returns None if not found."""
    import json as _json
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = _json.loads(tag.string or "")
        except Exception:
            continue
        # May be a list or a single object
        if isinstance(data, list):
            data = next((d for d in data if d.get("@type") == "Recipe"), None)
            if data is None:
                continue
        if data.get("@type") != "Recipe":
            continue
        # Found a schema.org/Recipe block
        return data
    return None


def _schema_org_to_recipe_out(data: dict, url: str) -> RecipeOut:
    import re as _re

    def _duration_to_mins(val: str | None) -> int | None:
        if not val:
            return None
        m = _re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', val)
        if not m:
            return None
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

    raw_ingredients = data.get("recipeIngredient", [])
    ingredients = [
        RecipeIngredientOut(
            api_ingredient_id="",
            canonical_name=ing.strip().lower()[:80],  # raw string — no NLP here
            quantity=0,
            unit="units",
        )
        for ing in raw_ingredients
    ]

    raw_instructions = data.get("recipeInstructions", [])
    instructions = []
    for i, step in enumerate(raw_instructions, 1):
        text = step.get("text", step) if isinstance(step, dict) else str(step)
        instructions.append(InstructionOut(step_number=i, phase="cook", text=text))

    yield_raw = data.get("recipeYield")
    yield_count = None
    if isinstance(yield_raw, list) and yield_raw:
        try:
            yield_count = int(str(yield_raw[0]).split()[0])
        except (ValueError, IndexError):
            pass
    elif yield_raw:
        try:
            yield_count = int(str(yield_raw).split()[0])
        except (ValueError, IndexError):
            pass

    return RecipeOut(
        external_id="",
        title=data.get("name", "Imported Recipe"),
        source_url=url,
        cuisine=data.get("recipeCuisine"),
        difficulty=None,
        active_time_mins=_duration_to_mins(data.get("prepTime")),
        total_time_mins=_duration_to_mins(data.get("totalTime")),
        dietary_flags=[],
        not_suitable_for=[],
        yield_count=yield_count,
        nutrition=NutritionOut(),
        instructions=instructions,
        ingredients=ingredients,
    )


def _api_recipe_to_out(api_recipe: RecipeApiRecipe, client: object) -> RecipeOut:
    return RecipeOut(
        external_id=api_recipe.id,
        title=api_recipe.name,
        source_url=api_recipe.source_url,
        cuisine=api_recipe.cuisine,
        difficulty=api_recipe.difficulty,
        active_time_mins=recipe_api_client.active_time_mins(api_recipe),
        total_time_mins=recipe_api_client.total_time_mins(api_recipe),
        dietary_flags=api_recipe.flags,
        not_suitable_for=api_recipe.not_suitable_for,
        yield_count=api_recipe.meta.yield_count,
        nutrition=NutritionOut(**api_recipe.nutrition.model_dump()),
        instructions=[InstructionOut(**i.model_dump()) for i in api_recipe.instructions],
        ingredients=[
            RecipeIngredientOut(
                api_ingredient_id=ing.ingredient_id,
                canonical_name=ing.name.lower(),
                quantity=ing.quantity or 0,
                unit=ing.unit or "units",
                preparation=ing.preparation,
                is_optional=ing.is_optional,
                substitutions=ing.substitutions,
            )
            for ing in api_recipe.ingredients
        ],
    )


@tracer.capture_method
def search_recipes(
    q: str | None,
    cuisine: str | None,
    dietary: str | None,
    page: int,
) -> RecipeSearchResponse:
    api_resp = recipe_api_client.search(q=q, cuisine=cuisine, dietary=dietary, page=page)
    results = [
        RecipeSearchResult(
            external_id=r.id,
            title=r.name,
            cuisine=r.cuisine,
            difficulty=r.difficulty,
            total_time_mins=_iso_to_mins(r.total_time),
            dietary_flags=r.flags,
        )
        for r in api_resp.results
    ]
    return RecipeSearchResponse(results=results, total=api_resp.total)


@tracer.capture_method
def get_recipe(recipe_id: str) -> RecipeOut:
    api_recipe = recipe_api_client.get_recipe(recipe_id)
    return _api_recipe_to_out(api_recipe, None)


@tracer.capture_method
def import_recipe_from_url(request: ImportUrlRequest) -> RecipeOut:
    url = request.url
    logger.info("importing recipe", extra={"url": url})

    try:
        _validate_url_ssrf(url)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Primary: schema.org/Recipe JSON-LD
    resp = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Glean/1.0"})
    resp.raise_for_status()
    schema_data = _parse_schema_org(resp.text)
    if schema_data:
        logger.info("recipe parsed via schema.org", extra={"url": url})
        return _schema_org_to_recipe_out(schema_data, url)

    # Fallback: Claude fetch tool
    logger.info("schema.org not found, using Claude fetch fallback", extra={"url": url})
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        tools=[{"type": "computer_20250124", "name": "str_replace_editor", "display_width_px": 1, "display_height_px": 1}],
        system=URL_PARSE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Parse the recipe at this URL: {url}"}],
    )
    # Claude returns structured JSON in its text response
    raw_text = next((b.text for b in message.content if hasattr(b, "text")), "{}")
    raw = json.loads(raw_text)
    logger.info("recipe url parse via Claude fallback", extra={"tokens": message.usage.input_tokens})

    return RecipeOut(
        external_id="",
        title=raw.get("title", "Imported Recipe"),
        source_url=url,
        cuisine=raw.get("cuisine"),
        difficulty=raw.get("difficulty"),
        active_time_mins=raw.get("active_time_mins"),
        total_time_mins=raw.get("total_time_mins"),
        dietary_flags=raw.get("dietary_flags", []),
        not_suitable_for=raw.get("not_suitable_for", []),
        yield_count=raw.get("yield_count"),
        nutrition=NutritionOut(**{k: raw.get("nutrition", {}).get(k, 0) for k in NutritionOut.model_fields}),
        instructions=[InstructionOut(**i) for i in raw.get("instructions", [])],
        ingredients=[
            RecipeIngredientOut(
                api_ingredient_id="",
                canonical_name=i["name"].lower(),
                quantity=i.get("quantity", 0),
                unit=i.get("unit", "units"),
                preparation=i.get("preparation"),
                is_optional=i.get("is_optional", False),
                substitutions=i.get("substitutions", []),
            )
            for i in raw.get("ingredients", [])
        ],
    )
```

- [ ] **Step 4: Write router.py**

```python
# backend/src/glean/recipes/router.py
from fastapi import APIRouter, Depends, Query
from glean.dependencies import verify_cognito_token
from glean.recipes import service
from glean.recipes.schemas import RecipeOut, RecipeSearchResponse, ImportUrlRequest

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("/search", response_model=RecipeSearchResponse, dependencies=[Depends(verify_cognito_token)])
def search_recipes(
    q: str | None = Query(None),
    cuisine: str | None = Query(None),
    dietary: str | None = Query(None),
    page: int = Query(1, ge=1),
) -> RecipeSearchResponse:
    return service.search_recipes(q=q, cuisine=cuisine, dietary=dietary, page=page)


@router.get("/{recipe_id}", response_model=RecipeOut, dependencies=[Depends(verify_cognito_token)])
def get_recipe(recipe_id: str) -> RecipeOut:
    return service.get_recipe(recipe_id)


@router.post("/import-url", response_model=RecipeOut, dependencies=[Depends(verify_cognito_token)])
def import_recipe_from_url(request: ImportUrlRequest) -> RecipeOut:
    return service.import_recipe_from_url(request)
```

- [ ] **Step 5: Register router in main.py**

```python
# backend/src/glean/main.py — add after receipts_router import
from glean.recipes.router import router as recipes_router
app.include_router(recipes_router)
```

- [ ] **Step 6: Write conftest.py and tests**

```python
# backend/tests/recipes/conftest.py
import pytest
from fastapi.testclient import TestClient
from glean.main import app
from glean.dependencies import verify_cognito_token


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[verify_cognito_token] = lambda: "test-user-sub"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict:
    return {}
```

```python
# backend/tests/recipes/test_router.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_search_recipes_returns_results(client: TestClient, auth_headers: dict) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = json.loads((FIXTURES / "recipe_search.json").read_text())
    mock_resp.raise_for_status = MagicMock()

    with patch("glean.recipe_api.client.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value = mock_resp
        # Re-initialise client with mock
        with patch("glean.recipes.service.recipe_api_client") as mock_api:
            from glean.recipe_api.schemas import RecipeApiSearchResponse, RecipeApiSearchResult
            mock_api.search.return_value = RecipeApiSearchResponse(
                results=[
                    RecipeApiSearchResult(id="abc-123", name="Spaghetti Carbonara", cuisine="Italian", difficulty="Easy", total_time="PT20M", flags=[]),
                ],
                total=1,
            )
            response = client.get("/recipes/search?q=carbonara", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Spaghetti Carbonara"
    assert response.json()["results"][0]["total_time_mins"] == 20


def test_get_recipe_returns_detail(client: TestClient, auth_headers: dict) -> None:
    detail = json.loads((FIXTURES / "recipe_detail.json").read_text())
    from glean.recipe_api.schemas import RecipeApiRecipe
    mock_recipe = RecipeApiRecipe(**detail)

    with patch("glean.recipes.service.recipe_api_client") as mock_api:
        mock_api.get_recipe.return_value = mock_recipe
        mock_api.active_time_mins.return_value = 15
        mock_api.total_time_mins.return_value = 20
        response = client.get("/recipes/abc-123", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Spaghetti Carbonara"
    assert len(body["ingredients"]) == 2
    assert body["nutrition"]["calories"] == 520


def test_search_requires_auth(client: TestClient) -> None:
    response = client.get("/recipes/search?q=pasta")
    assert response.status_code == 401


def test_import_url_rejects_http(client: TestClient, auth_headers: dict) -> None:
    response = client.post(
        "/recipes/import-url",
        headers=auth_headers,
        json={"url": "http://example.com/recipe"},
    )
    assert response.status_code == 400
    assert "HTTPS" in response.json()["detail"]


def test_import_url_rejects_private_ip(client: TestClient, auth_headers: dict) -> None:
    with patch("glean.recipes.service.socket.gethostbyname", return_value="192.168.1.1"):
        response = client.post(
            "/recipes/import-url",
            headers=auth_headers,
            json={"url": "https://internal.example.com/recipe"},
        )
    assert response.status_code == 400
    assert "not routable" in response.json()["detail"]


def test_import_url_uses_schema_org(client: TestClient, auth_headers: dict) -> None:
    html_with_jsonld = """<html><head>
    <script type="application/ld+json">
    {"@type": "Recipe", "name": "Schema Carbonara", "recipeIngredient": ["200g spaghetti"],
     "recipeInstructions": [{"@type": "HowToStep", "text": "Cook pasta."}],
     "recipeYield": "2", "recipeCuisine": "Italian"}
    </script></head><body></body></html>"""
    mock_http = MagicMock()
    mock_http.text = html_with_jsonld
    mock_http.raise_for_status = MagicMock()

    with patch("glean.recipes.service.socket.gethostbyname", return_value="93.184.216.34"), \
         patch("httpx.get", return_value=mock_http), \
         patch("anthropic.Anthropic") as MockAnthropic:
        response = client.post(
            "/recipes/import-url",
            headers=auth_headers,
            json={"url": "https://example.com/carbonara"},
        )
        # schema.org path taken — Claude should NOT be called
        MockAnthropic.assert_not_called()

    assert response.status_code == 200
    assert response.json()["title"] == "Schema Carbonara"
    assert response.json()["cuisine"] == "Italian"
    assert response.json()["ingredients"][0]["canonical_name"] == "200g spaghetti"


def test_import_url_parses_recipe(client: TestClient, auth_headers: dict) -> None:
    """Claude fallback path — no JSON-LD in HTML."""
    mock_html = "<html><body>Carbonara recipe page</body></html>"
    mock_http = MagicMock()
    mock_http.text = mock_html
    mock_http.raise_for_status = MagicMock()

    claude_output = {
        "title": "Carbonara", "cuisine": "Italian", "difficulty": "Easy",
        "active_time_mins": 15, "total_time_mins": 20, "yield_count": 2,
        "dietary_flags": [], "not_suitable_for": [],
        "ingredients": [{"name": "spaghetti", "quantity": 200, "unit": "g", "is_optional": False, "substitutions": []}],
        "instructions": [{"step_number": 1, "phase": "cook", "text": "Cook pasta."}],
        "nutrition": {"calories": 500, "protein_g": 20, "carbohydrates_g": 60, "fat_g": 15, "fiber_g": 2, "sugar_g": 1, "sodium_mg": 300},
    }
    mock_content = MagicMock()
    mock_content.text = json.dumps(claude_output)
    mock_msg = MagicMock()
    mock_msg.content = [mock_content]
    mock_msg.usage.input_tokens = 800

    with patch("glean.recipes.service.socket.gethostbyname", return_value="93.184.216.34"), \
         patch("httpx.get", return_value=mock_http), \
         patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_msg
        response = client.post(
            "/recipes/import-url",
            headers=auth_headers,
            json={"url": "https://example.com/carbonara"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Carbonara"
    assert response.json()["ingredients"][0]["canonical_name"] == "spaghetti"
```

- [ ] **Step 7: Run tests**

```bash
cd backend && uv run pytest tests/recipes/ -v
```
Expected: 8 passing (7 router + 4 client — search, detail, auth guard, 3 import-url SSRF/schema.org/Claude-fallback)

- [ ] **Step 8: Commit**

```bash
git add backend/src/glean/recipes/ backend/tests/recipes/
git commit -m "🍽 recipes: search, fetch, and URL import endpoints"
```

---

### Task 3: Mobile — recipe SQLite queries

**Files:**
- Create: `mobile/src/db/recipes.ts`

- [ ] **Step 1: Write recipes.ts**

```typescript
// mobile/src/db/recipes.ts
import { getDb } from './client';
import { resolveOrCreateIngredient } from './ingredients';
import type { Recipe, RecipeIngredient } from '@/types';

export async function getSavedRecipes(): Promise<Recipe[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<Recipe & { not_suitable_for: string; instructions: string; nutrition: string }>(
    'SELECT * FROM recipes ORDER BY last_cooked_at ASC NULLS LAST, title ASC'
  );
  return Promise.all(rows.map(async r => {
    const flagRows = await db.getAllAsync<{ flag: string }>(
      'SELECT flag FROM recipe_dietary_flags WHERE recipe_id = ?', [r.id]
    );
    return {
      ...r,
      dietary_flags: flagRows.map(f => f.flag),
      not_suitable_for: JSON.parse(r.not_suitable_for),
      instructions: JSON.parse(r.instructions),
      nutrition: r.nutrition ? JSON.parse(r.nutrition) : null,
      is_ai_generated: Boolean(r.is_ai_generated),
    };
  }));
}

export async function getRecipeById(id: number): Promise<Recipe | null> {
  const db = await getDb();
  const row = await db.getFirstAsync<Recipe & { not_suitable_for: string; instructions: string; nutrition: string }>(
    'SELECT * FROM recipes WHERE id = ?', [id]
  );
  if (!row) return null;
  const flagRows = await db.getAllAsync<{ flag: string }>(
    'SELECT flag FROM recipe_dietary_flags WHERE recipe_id = ?', [id]
  );
  return {
    ...row,
    dietary_flags: flagRows.map(f => f.flag),
    not_suitable_for: JSON.parse(row.not_suitable_for),
    instructions: JSON.parse(row.instructions),
    nutrition: row.nutrition ? JSON.parse(row.nutrition) : null,
    is_ai_generated: Boolean(row.is_ai_generated),
  };
}

export async function getRecipeByExternalId(externalId: string): Promise<Recipe | null> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ id: number }>(
    'SELECT id FROM recipes WHERE external_id = ?', [externalId]
  );
  if (!row) return null;
  return getRecipeById(row.id);
}

export interface SaveRecipeParams {
  external_id?: string;
  title: string;
  source_url?: string | null;
  cuisine?: string | null;
  difficulty?: string | null;
  active_time_mins?: number | null;
  total_time_mins?: number | null;
  dietary_flags?: string[];
  not_suitable_for?: string[];
  yield_count?: number | null;
  nutrition?: object | null;
  instructions?: object[];
  is_ai_generated?: boolean;
  ingredients: Array<{
    api_ingredient_id?: string | null;
    canonical_name: string;
    quantity: number;
    unit: string;
    preparation?: string | null;
    is_optional?: boolean;
    substitutions?: string[];
  }>;
}

export async function saveRecipe(params: SaveRecipeParams): Promise<number> {
  const db = await getDb();

  const result = await db.runAsync(
    `INSERT OR REPLACE INTO recipes
     (external_id, title, source_url, cuisine, difficulty, active_time_mins, total_time_mins,
      not_suitable_for, yield_count, nutrition, instructions, is_ai_generated)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      params.external_id ?? null,
      params.title,
      params.source_url ?? null,
      params.cuisine ?? null,
      params.difficulty ?? null,
      params.active_time_mins ?? null,
      params.total_time_mins ?? null,
      JSON.stringify(params.not_suitable_for ?? []),
      params.yield_count ?? null,
      params.nutrition ? JSON.stringify(params.nutrition) : null,
      JSON.stringify(params.instructions ?? []),
      params.is_ai_generated ? 1 : 0,
    ]
  );

  const recipeId = result.lastInsertRowId;

  // Save dietary flags as separate rows
  for (const flag of (params.dietary_flags ?? [])) {
    await db.runAsync(
      'INSERT OR IGNORE INTO recipe_dietary_flags (recipe_id, flag) VALUES (?, ?)',
      [recipeId, flag]
    );
  }

  for (const ing of params.ingredients) {
    const ingredientId = await resolveOrCreateIngredient({
      canonical_name: ing.canonical_name,
      api_ingredient_id: ing.api_ingredient_id,
    });
    await db.runAsync(
      `INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit, preparation, is_optional, substitutions)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [recipeId, ingredientId, ing.quantity, ing.unit, ing.preparation ?? null, ing.is_optional ? 1 : 0, JSON.stringify(ing.substitutions ?? [])]
    );
  }

  return recipeId;
}

export async function getRecipeIngredients(recipeId: number): Promise<RecipeIngredient[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<RecipeIngredient & { substitutions: string }>(
    `SELECT ri.*, i.canonical_name
     FROM recipe_ingredients ri
     JOIN ingredients i ON ri.ingredient_id = i.id
     WHERE ri.recipe_id = ?`,
    [recipeId]
  );
  return rows.map(r => ({ ...r, substitutions: JSON.parse(r.substitutions), is_optional: Boolean(r.is_optional) }));
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/recipes.test.ts
import { saveRecipe, getRecipeByExternalId } from '@/db/recipes';
import { getDb } from '@/db/client';
import { resolveOrCreateIngredient } from '@/db/ingredients';

jest.mock('@/db/client');
jest.mock('@/db/ingredients');

describe('saveRecipe', () => {
  it('inserts recipe and its ingredients, returns new id', async () => {
    const mockDb = {
      runAsync: jest.fn()
        .mockResolvedValueOnce({ lastInsertRowId: 42 })   // recipe insert
        .mockResolvedValue({}),                            // flag + ingredient inserts
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    const id = await saveRecipe({
      title: 'Pasta',
      ingredients: [{ canonical_name: 'spaghetti', quantity: 200, unit: 'g' }],
    });

    expect(id).toBe(42);
    // 1 recipe insert + 1 ingredient insert (no flags)
    expect(mockDb.runAsync).toHaveBeenCalledTimes(2);
  });

  it('inserts each dietary flag into recipe_dietary_flags', async () => {
    const mockDb = { runAsync: jest.fn().mockResolvedValue({ lastInsertRowId: 1 }) };
    (getDb as jest.Mock).mockResolvedValue(mockDb);
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    await saveRecipe({
      title: 'GF Pasta',
      dietary_flags: ['Gluten-Free', 'Vegan'],
      ingredients: [{ canonical_name: 'rice pasta', quantity: 200, unit: 'g' }],
    });

    // 1 recipe insert + 2 flag inserts + 1 ingredient insert = 4 calls
    expect(mockDb.runAsync).toHaveBeenCalledTimes(4);
    expect(mockDb.runAsync).toHaveBeenCalledWith(
      'INSERT OR IGNORE INTO recipe_dietary_flags (recipe_id, flag) VALUES (?, ?)',
      [1, 'Gluten-Free']
    );
    expect(mockDb.runAsync).toHaveBeenCalledWith(
      'INSERT OR IGNORE INTO recipe_dietary_flags (recipe_id, flag) VALUES (?, ?)',
      [1, 'Vegan']
    );
  });

  it('does not include dietary_flags in the recipes INSERT', async () => {
    const mockDb = { runAsync: jest.fn().mockResolvedValue({ lastInsertRowId: 1 }) };
    (getDb as jest.Mock).mockResolvedValue(mockDb);
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    await saveRecipe({
      title: 'GF Pasta',
      dietary_flags: ['Gluten-Free'],
      ingredients: [{ canonical_name: 'rice pasta', quantity: 200, unit: 'g' }],
    });

    const recipeInsertCall = mockDb.runAsync.mock.calls.find(
      ([sql]: [string]) => sql.includes('INSERT OR REPLACE INTO recipes')
    );
    expect(recipeInsertCall).toBeDefined();
    // dietary_flags column must not appear in the INSERT statement
    expect(recipeInsertCall[0]).not.toContain('dietary_flags');
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/recipes.test.ts --verbose
```
Expected: 3 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/recipes.ts mobile/src/__tests__/db/recipes.test.ts
git commit -m "🗄️ db: recipe SQLite queries with ingredient resolution"
```

---

### Task 4: Mobile — recipe list screen

**Files:**
- Modify: `mobile/app/(tabs)/meals/index.tsx`

- [ ] **Step 1: Write meals/index.tsx**

```typescript
// mobile/app/(tabs)/meals/index.tsx
import { useState, useCallback } from 'react';
import { View, Text, FlatList, Pressable, TextInput, StyleSheet, ActivityIndicator } from 'react-native';
import { useFocusEffect, router } from 'expo-router';
import { getSavedRecipes } from '@/db/recipes';
import type { Recipe } from '@/types';

export default function MealsScreen() {
  const [tab, setTab] = useState<'saved' | 'search'>('saved');
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setRecipes(await getSavedRecipes());
    setLoading(false);
  }, []);

  useFocusEffect(load);

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Meals</Text>
      <View style={styles.tabs}>
        {(['saved', 'search'] as const).map(t => (
          <Pressable key={t} style={[styles.tab, tab === t && styles.tabActive]} onPress={() => setTab(t)}>
            <Text style={tab === t ? styles.tabTextActive : styles.tabText}>
              {t === 'saved' ? 'My Recipes' : 'Discover'}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === 'saved' ? (
        loading ? <ActivityIndicator style={{ flex: 1 }} /> : (
          <FlatList
            data={recipes}
            keyExtractor={r => String(r.id)}
            renderItem={({ item }) => (
              <Pressable style={styles.recipeRow} onPress={() => router.push(`/(tabs)/meals/${item.id}`)}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recipeTitle}>{item.title}</Text>
                  <Text style={styles.recipeMeta}>
                    {[item.cuisine, item.difficulty, item.total_time_mins ? `${item.total_time_mins}min` : null]
                      .filter(Boolean).join(' · ')}
                  </Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </Pressable>
            )}
            ListEmptyComponent={
              <Text style={styles.empty}>No recipes yet. Discover some or import via URL.</Text>
            }
          />
        )
      ) : (
        <Pressable style={styles.discoverButton} onPress={() => router.push('/(tabs)/meals/search')}>
          <Text style={styles.discoverText}>Search recipes →</Text>
        </Pressable>
      )}

      <Pressable style={styles.importButton} onPress={() => router.push('/(tabs)/meals/search')}>
        <Text style={styles.importText}>Import from URL</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  heading: { fontSize: 24, fontWeight: '700', padding: 16 },
  tabs: { flexDirection: 'row', paddingHorizontal: 16, marginBottom: 8, gap: 8 },
  tab: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: '#f5f5f5', alignItems: 'center' },
  tabActive: { backgroundColor: '#2a9d8f' },
  tabText: { color: '#666', fontWeight: '600' },
  tabTextActive: { color: '#fff', fontWeight: '600' },
  recipeRow: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee' },
  recipeTitle: { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  recipeMeta: { fontSize: 12, color: '#888' },
  chevron: { fontSize: 20, color: '#ccc' },
  empty: { textAlign: 'center', color: '#888', marginTop: 40, fontSize: 14 },
  discoverButton: { margin: 16, padding: 14, borderRadius: 8, borderWidth: 1, borderColor: '#2a9d8f', alignItems: 'center' },
  discoverText: { color: '#2a9d8f', fontWeight: '600' },
  importButton: { margin: 16, marginTop: 0, padding: 14, borderRadius: 8, backgroundColor: '#f5f5f5', alignItems: 'center' },
  importText: { color: '#444', fontWeight: '600' },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/app/(tabs)/meals/index.tsx
git commit -m "🍽 meals: saved recipe list with saved/discover tabs"
```

---

### Task 5: Mobile — recipe detail + search screens

**Files:**
- Create: `mobile/app/(tabs)/meals/[id].tsx`
- Create: `mobile/app/(tabs)/meals/search.tsx`

- [ ] **Step 1: Write [id].tsx (recipe detail)**

```typescript
// mobile/app/(tabs)/meals/[id].tsx
import { useEffect, useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { getRecipeById, getRecipeIngredients } from '@/db/recipes';
import type { Recipe, RecipeIngredient } from '@/types';

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const r = await getRecipeById(Number(id));
      if (!r) { router.back(); return; }
      setRecipe(r);
      setIngredients(await getRecipeIngredients(Number(id)));
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;
  if (!recipe) return null;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{recipe.title}</Text>
      <Text style={styles.meta}>
        {[recipe.cuisine, recipe.difficulty, recipe.total_time_mins ? `${recipe.total_time_mins} min` : null]
          .filter(Boolean).join(' · ')}
      </Text>
      {recipe.dietary_flags.length > 0 && (
        <View style={styles.flags}>
          {recipe.dietary_flags.map(f => (
            <View key={f} style={styles.flag}><Text style={styles.flagText}>{f}</Text></View>
          ))}
        </View>
      )}

      <Text style={styles.sectionHeading}>Ingredients</Text>
      {ingredients.map(ing => (
        <Text key={ing.id} style={styles.ingredient}>
          • {ing.quantity}{ing.unit} {ing.canonical_name}
          {ing.preparation ? `, ${ing.preparation}` : ''}
          {ing.is_optional ? ' (optional)' : ''}
        </Text>
      ))}

      <Text style={styles.sectionHeading}>Instructions</Text>
      {recipe.instructions.map(step => (
        <View key={step.step_number} style={styles.step}>
          <Text style={styles.stepNum}>{step.step_number}</Text>
          <Text style={styles.stepText}>{step.text}</Text>
        </View>
      ))}

      <Pressable
        style={styles.addToPlanButton}
        onPress={() => router.push({ pathname: '/(tabs)/plan', params: { add_recipe_id: id } })}
      >
        <Text style={styles.addToPlanText}>Add to Plan</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 16 },
  title: { fontSize: 22, fontWeight: '700', marginBottom: 6 },
  meta: { fontSize: 13, color: '#888', marginBottom: 10 },
  flags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 16 },
  flag: { backgroundColor: '#e8f5f3', borderRadius: 12, paddingHorizontal: 8, paddingVertical: 3 },
  flagText: { fontSize: 11, color: '#2a9d8f' },
  sectionHeading: { fontSize: 16, fontWeight: '700', marginTop: 20, marginBottom: 10 },
  ingredient: { fontSize: 14, marginBottom: 4, color: '#333' },
  step: { flexDirection: 'row', marginBottom: 12, gap: 12 },
  stepNum: { width: 24, height: 24, borderRadius: 12, backgroundColor: '#2a9d8f', color: '#fff', textAlign: 'center', lineHeight: 24, fontWeight: '700', fontSize: 12 },
  stepText: { flex: 1, fontSize: 14, lineHeight: 20, color: '#333' },
  addToPlanButton: { margin: 16, marginTop: 24, backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center' },
  addToPlanText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
```

- [ ] **Step 2: Write search.tsx**

```typescript
// mobile/app/(tabs)/meals/search.tsx
import { useState } from 'react';
import {
  View, Text, TextInput, FlatList, Pressable,
  StyleSheet, ActivityIndicator, Alert
} from 'react-native';
import { router } from 'expo-router';
import { apiClient } from '@/api/client';
import { saveRecipe, getRecipeByExternalId } from '@/db/recipes';

interface SearchResult {
  external_id: string;
  title: string;
  cuisine: string | null;
  difficulty: string | null;
  total_time_mins: number | null;
  dietary_flags: string[];
}

export default function SearchScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [importUrl, setImportUrl] = useState('');
  const [importing, setImporting] = useState(false);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await apiClient.get<{ results: SearchResult[] }>(`/recipes/search?q=${encodeURIComponent(query)}`);
      setResults(data.results);
    } catch { Alert.alert('Search failed'); }
    finally { setLoading(false); }
  }

  async function addRecipe(result: SearchResult) {
    // Check cache first
    const cached = await getRecipeByExternalId(result.external_id);
    if (cached) { router.push(`/(tabs)/meals/${cached.id}`); return; }

    // Fetch full detail (1 credit) and cache it
    try {
      const detail = await apiClient.get<any>(`/recipes/${result.external_id}`);
      const id = await saveRecipe({ ...detail, title: detail.title, ingredients: detail.ingredients });
      router.push(`/(tabs)/meals/${id}`);
    } catch { Alert.alert('Failed to fetch recipe details.'); }
  }

  async function importFromUrl() {
    if (!importUrl.trim()) return;
    setImporting(true);
    try {
      const detail = await apiClient.post<any>('/recipes/import-url', { url: importUrl.trim() });
      const id = await saveRecipe({ ...detail, title: detail.title, ingredients: detail.ingredients });
      router.push(`/(tabs)/meals/${id}`);
    } catch { Alert.alert('Import failed', 'Could not parse the recipe. Try a different URL.'); }
    finally { setImporting(false); }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Discover Recipes</Text>

      <View style={styles.searchRow}>
        <TextInput style={styles.searchInput} value={query} onChangeText={setQuery} placeholder="Search recipes…" returnKeyType="search" onSubmitEditing={search} />
        <Pressable style={styles.searchBtn} onPress={search}><Text style={styles.searchBtnText}>Go</Text></Pressable>
      </View>

      {loading ? <ActivityIndicator style={{ marginTop: 20 }} /> : (
        <FlatList
          data={results}
          keyExtractor={r => r.external_id}
          renderItem={({ item }) => (
            <Pressable style={styles.result} onPress={() => addRecipe(item)}>
              <Text style={styles.resultTitle}>{item.title}</Text>
              <Text style={styles.resultMeta}>{[item.cuisine, item.difficulty, item.total_time_mins ? `${item.total_time_mins}min` : null].filter(Boolean).join(' · ')}</Text>
            </Pressable>
          )}
        />
      )}

      <View style={styles.importSection}>
        <Text style={styles.importLabel}>Import from URL</Text>
        <TextInput style={styles.importInput} value={importUrl} onChangeText={setImportUrl} placeholder="https://..." autoCapitalize="none" keyboardType="url" />
        <Pressable style={styles.importBtn} onPress={importFromUrl} disabled={importing}>
          {importing ? <ActivityIndicator color="#fff" /> : <Text style={styles.importBtnText}>Import</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 16 },
  heading: { fontSize: 22, fontWeight: '700', marginBottom: 16 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  searchInput: { flex: 1, borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, fontSize: 15 },
  searchBtn: { backgroundColor: '#2a9d8f', borderRadius: 8, paddingHorizontal: 16, justifyContent: 'center' },
  searchBtnText: { color: '#fff', fontWeight: '600' },
  result: { padding: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee' },
  resultTitle: { fontSize: 15, fontWeight: '600', marginBottom: 2 },
  resultMeta: { fontSize: 12, color: '#888' },
  importSection: { borderTopWidth: 1, borderColor: '#eee', paddingTop: 16, marginTop: 8 },
  importLabel: { fontSize: 14, fontWeight: '600', marginBottom: 8 },
  importInput: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, fontSize: 14, marginBottom: 8 },
  importBtn: { backgroundColor: '#2a9d8f', borderRadius: 8, padding: 12, alignItems: 'center' },
  importBtnText: { color: '#fff', fontWeight: '600' },
});
```

- [ ] **Step 3: Commit**

```bash
git add mobile/app/(tabs)/meals/
git commit -m "🔍 meals: recipe detail and search/import screens"
```
