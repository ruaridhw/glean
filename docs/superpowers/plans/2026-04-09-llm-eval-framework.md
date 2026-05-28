# LLM Evaluation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a three-layer evaluation framework (structural, heuristic, LLM-as-judge) for all Claude integrations, with LangSmith tracing and production monitoring.

**Architecture:** Refactor hardcoded `ChatAnthropic` usage to a model-agnostic factory, add LangSmith tracing via environment config, create pytest-based eval suites with golden datasets, and add a manual CI workflow that posts jazzy PR comments.

**Tech Stack:** Python 3.14, pytest, LangChain (langchain-anthropic, langchain-google-genai), LangSmith SDK, GitHub Actions

---

## File Structure

### New files
```
backend/src/glean/llm.py                      # Model factory (create_chat_model)
backend/tests/evals/__init__.py                # Eval package marker
backend/tests/evals/conftest.py                # Eval fixtures: load datasets, init model
backend/tests/evals/test_receipt_scan.py        # Receipt eval suite (all 3 layers)
backend/tests/evals/test_suggestions.py         # Suggestions eval suite (all 3 layers)
backend/tests/evals/test_recipe_import.py       # Recipe import eval suite (all 3 layers)
backend/tests/evals/judges/__init__.py          # Judge package marker
backend/tests/evals/judges/rubrics.py           # LLM-as-judge prompts and scoring
backend/tests/evals/fixtures/receipt_scan.json   # Golden dataset: receipt scanning
backend/tests/evals/fixtures/suggestions.json    # Golden dataset: meal suggestions
backend/tests/evals/fixtures/recipe_import.json  # Golden dataset: recipe import
backend/scripts/sync_eval_datasets.py            # One-way push: git fixtures → LangSmith
.github/workflows/llm-evals.yml                 # Manual eval workflow
```

### Modified files
```
backend/src/glean/config.py                     # Add llm_provider, llm_model settings
backend/src/glean/receipts/service.py            # Use create_chat_model + trace metadata
backend/src/glean/suggestions/service.py         # Use create_chat_model + trace metadata
backend/src/glean/recipes/service.py             # Use create_chat_model + trace metadata
backend/pyproject.toml                           # Add langsmith, langchain-google-genai deps
backend/.env.example                             # Add new env vars
```

---

### Task 1: Add LLM settings to config

**Files:**
- Modify: `backend/src/glean/config.py:34-44`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add new settings fields to Settings class**

In `backend/src/glean/config.py`, add three new fields to the `Settings` class after `rate_limit_per_hour`:

```python
class Settings(BaseSettings):
    anthropic_api_key: str
    recipe_api_key: str
    recipe_api_base_url: str = "https://recipe-api.com/api/v1"
    aws_region: str = "eu-west-2"
    cognito_user_pool_id: str
    cognito_app_client_id: str
    s3_receipts_bucket: str
    log_level: str = "INFO"
    rate_limit_per_hour: int = 20
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    langchain_project: str = "glean-dev"
```

- [ ] **Step 2: Update .env.example with new variables**

Append to `backend/.env.example`:

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=glean-dev
```

- [ ] **Step 3: Verify settings load correctly**

Run: `cd backend && uv run python -c "from glean.config import Settings; print('OK')"`
Expected: `OK` (settings will fail to instantiate without env vars, but the import should succeed)

- [ ] **Step 4: Commit**

```bash
git add backend/src/glean/config.py backend/.env.example
git commit -m "⚙️ feat: add LLM provider and model settings to config"
```

---

### Task 2: Create model factory

**Files:**
- Create: `backend/src/glean/llm.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Write the failing test for create_chat_model**

Create `backend/tests/test_llm.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.language_models import BaseChatModel

from glean.llm import create_chat_model


class TestCreateChatModel:
    def test_anthropic_returns_chat_anthropic(self) -> None:
        with patch("glean.llm.ChatAnthropic") as mock_cls:
            model = create_chat_model("anthropic", "claude-sonnet-4-6", api_key="test-key")
            mock_cls.assert_called_once_with(model="claude-sonnet-4-6", api_key="test-key")
            assert model is mock_cls.return_value

    def test_google_returns_chat_google(self) -> None:
        with patch("glean.llm.ChatGoogleGenerativeAI") as mock_cls:
            model = create_chat_model("google", "gemma-3", api_key="test-key")
            mock_cls.assert_called_once_with(model="gemma-3", api_key="test-key")
            assert model is mock_cls.return_value

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider: foobar"):
            create_chat_model("foobar", "some-model", api_key="test-key")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'glean.llm'`

- [ ] **Step 3: Write the model factory**

Create `backend/src/glean/llm.py`:

```python
from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel


def create_chat_model(provider: str, model: str, *, api_key: str) -> BaseChatModel:
    match provider:
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")
```

Note: `ChatGoogleGenerativeAI` is lazily imported so it's only required when actually used (it's a dev-only dependency).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_llm.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/glean/llm.py backend/tests/test_llm.py
git commit -m "🏗️ feat: add model-agnostic LLM factory with provider switching"
```

---

### Task 3: Refactor services to use model factory

**Files:**
- Modify: `backend/src/glean/receipts/service.py:8-9,65,75`
- Modify: `backend/src/glean/suggestions/service.py:3-4,29`
- Modify: `backend/src/glean/recipes/service.py:12-13,269`

- [ ] **Step 1: Refactor receipts/service.py**

Replace the ChatAnthropic import and usages:

In `backend/src/glean/receipts/service.py`, replace:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
```
with:

```python
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
from glean.llm import create_chat_model
```

Replace line 65:
```python
    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key)
```
with:
```python
    model = create_chat_model(settings.llm_provider, settings.llm_model, api_key=settings.anthropic_api_key)
```

Add trace metadata to the invoke call on line 66. Replace:
```python
    result = model.invoke([SystemMessage(content=NORMALISE_SYSTEM_PROMPT), HumanMessage(content=json.dumps(lines))])
```
with:
```python
    result = model.invoke(
        [SystemMessage(content=NORMALISE_SYSTEM_PROMPT), HumanMessage(content=json.dumps(lines))],
        config={"metadata": {"feature": "receipt-scan"}},
    )
```

Replace line 75:
```python
    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key)
```
with:
```python
    model = create_chat_model(settings.llm_provider, settings.llm_model, api_key=settings.anthropic_api_key)
```

Add metadata to the describe_purchase invoke call. Replace lines 76-81:
```python
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {request.text}"),
        ]
    )
```
with:
```python
    result = model.invoke(
        [
            SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this grocery purchase description: {request.text}"),
        ],
        config={"metadata": {"feature": "receipt-scan"}},
    )
```

- [ ] **Step 2: Refactor suggestions/service.py**

In `backend/src/glean/suggestions/service.py`, replace:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
```
with:

```python
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
from glean.llm import create_chat_model
```

Replace line 29:
```python
    model = ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key)
```
with:
```python
    model = create_chat_model(settings.llm_provider, settings.llm_model, api_key=settings.anthropic_api_key)
```

Add metadata to the invoke call. Replace lines 49-54:
```python
    result = model.invoke(
        [
            SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ]
    )
```
with:
```python
    result = model.invoke(
        [
            SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context, default=str)),
        ],
        config={"metadata": {"feature": "suggestions"}},
    )
```

- [ ] **Step 3: Refactor recipes/service.py**

In `backend/src/glean/recipes/service.py`, replace:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
```
with:

```python
from langchain_core.messages import HumanMessage, SystemMessage

from glean.config import get_settings
from glean.llm import create_chat_model
```

Replace line 269:
```python
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=settings.anthropic_api_key)
```
with:
```python
    llm = create_chat_model(settings.llm_provider, settings.llm_model, api_key=settings.anthropic_api_key)
```

Add metadata to the invoke call. Replace lines 270-275:
```python
    response = llm.invoke(
        [
            SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this HTML:\n\n{html[:8000]}"),
        ]
    )
```
with:
```python
    response = llm.invoke(
        [
            SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this HTML:\n\n{html[:8000]}"),
        ],
        config={"metadata": {"feature": "recipe-import"}},
    )
```

- [ ] **Step 4: Update existing test mocks to patch the new import path**

The existing tests patch `glean.receipts.service.ChatAnthropic`, `glean.suggestions.service.ChatAnthropic`, and `glean.recipes.service.ChatAnthropic`. Since we removed the direct import, we now need to patch `glean.llm.create_chat_model` in each service module.

In `backend/tests/receipts/test_router.py`, replace:
```python
        patch("glean.receipts.service.ChatAnthropic") as MockChatAnthropic,
    ):
        MockChatAnthropic.return_value.invoke.return_value = mock_result
```
with:
```python
        patch("glean.receipts.service.create_chat_model") as mock_create,
    ):
        mock_create.return_value.invoke.return_value = mock_result
```

And for the second test (`test_describe_purchase_parses_text`), replace:
```python
    with patch("glean.receipts.service.ChatAnthropic") as MockChatAnthropic:
        MockChatAnthropic.return_value.invoke.return_value = mock_result
```
with:
```python
    with patch("glean.receipts.service.create_chat_model") as mock_create:
        mock_create.return_value.invoke.return_value = mock_result
```

In `backend/tests/suggestions/test_router.py`, replace:
```python
    with patch("glean.suggestions.service.ChatAnthropic") as MockChatAnthropic:
        MockChatAnthropic.return_value.invoke.return_value = mock_result
```
with:
```python
    with patch("glean.suggestions.service.create_chat_model") as mock_create:
        mock_create.return_value.invoke.return_value = mock_result
```

In `backend/tests/recipes/test_router.py`, find the test `test_import_url_falls_back_to_claude` and replace:
```python
        patch("glean.recipes.service.ChatAnthropic") as MockLLM,
```
with:
```python
        patch("glean.recipes.service.create_chat_model") as MockLLM,
```

And replace:
```python
        MockLLM.return_value.invoke.return_value = mock_claude_response
```
(This line stays the same — MockLLM.return_value.invoke.return_value is the same pattern.)

- [ ] **Step 5: Run full test suite to verify nothing broke**

Run: `cd backend && uv run pytest -v`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/src/glean/receipts/service.py backend/src/glean/suggestions/service.py backend/src/glean/recipes/service.py backend/tests/receipts/test_router.py backend/tests/suggestions/test_router.py backend/tests/recipes/test_router.py
git commit -m "♻️ refactor: replace hardcoded ChatAnthropic with model factory + trace metadata"
```

---

### Task 4: Add dependencies

**Files:**
- Modify: `backend/pyproject.toml:5-18,20-30`

- [ ] **Step 1: Add langsmith to production dependencies**

In `backend/pyproject.toml`, add to the `dependencies` list after `langchain-anthropic`:

```toml
    "langsmith>=0.3.0,<1",
```

- [ ] **Step 2: Add langchain-google-genai to dev dependencies**

In `backend/pyproject.toml`, add to the `[project.optional-dependencies] dev` list:

```toml
    "langchain-google-genai>=2.1.0,<3",
```

And add to the `[dependency-groups] dev` list:

```toml
    "langchain-google-genai>=2.1.0,<3",
```

- [ ] **Step 3: Add custom pytest marker registration**

In `backend/pyproject.toml`, add to `[tool.pytest.ini_options]`:

```toml
markers = ["soft_gate: marks tests as soft-gate evaluations (deselect with '-m \"not soft_gate\"')"]
```

- [ ] **Step 4: Install new dependencies**

Run: `cd backend && uv sync --all-extras`
Expected: Dependencies resolve and install successfully

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "📌 deps: add langsmith and langchain-google-genai for eval framework"
```

---

### Task 5: Create golden eval datasets

**Files:**
- Create: `backend/tests/evals/__init__.py`
- Create: `backend/tests/evals/fixtures/receipt_scan.json`
- Create: `backend/tests/evals/fixtures/suggestions.json`
- Create: `backend/tests/evals/fixtures/recipe_import.json`

- [ ] **Step 1: Create the eval package**

Create empty `backend/tests/evals/__init__.py`.

- [ ] **Step 2: Create receipt_scan golden dataset**

Create `backend/tests/evals/fixtures/receipt_scan.json`:

```json
[
  {
    "input": {
      "line_items": [
        {"name": "BNLS CHKN BRST 500G", "quantity_raw": "1", "price": "3.50"},
        {"name": "WHL MILK 2L", "quantity_raw": "2", "price": "1.35"}
      ]
    },
    "expected": {
      "items": [
        {"name": "chicken breast", "quantity": 500, "unit": "g", "unit_price": 0.007, "confidence": 0.92},
        {"name": "whole milk", "quantity": 2000, "unit": "ml", "unit_price": 0.000675, "confidence": 0.97}
      ]
    }
  },
  {
    "input": {
      "line_items": [
        {"name": "ORG BANANAS x5", "quantity_raw": "5", "price": "1.20"},
        {"name": "BROCCOLI 350G", "quantity_raw": "1", "price": "0.89"}
      ]
    },
    "expected": {
      "items": [
        {"name": "banana", "quantity": 5, "unit": "units", "unit_price": 0.24, "confidence": 0.95},
        {"name": "broccoli", "quantity": 350, "unit": "g", "unit_price": 0.00254, "confidence": 0.93}
      ]
    }
  },
  {
    "input": {
      "line_items": [
        {"name": "FREE RANGE EGGS x12", "quantity_raw": "1", "price": "3.20"},
        {"name": "CHEDDAR CHEESE 400G", "quantity_raw": "1", "price": "2.75"},
        {"name": "OLIVE OIL 500ML", "quantity_raw": "1", "price": "4.50"}
      ]
    },
    "expected": {
      "items": [
        {"name": "free range eggs", "quantity": 12, "unit": "units", "unit_price": 0.2667, "confidence": 0.94},
        {"name": "cheddar cheese", "quantity": 400, "unit": "g", "unit_price": 0.006875, "confidence": 0.95},
        {"name": "olive oil", "quantity": 500, "unit": "ml", "unit_price": 0.009, "confidence": 0.96}
      ]
    }
  },
  {
    "input": {
      "line_items": [
        {"name": "BASMATI RICE 1KG", "quantity_raw": "1", "price": "1.89"},
        {"name": "TINNED TOMS 4PK", "quantity_raw": "1", "price": "2.00"}
      ]
    },
    "expected": {
      "items": [
        {"name": "basmati rice", "quantity": 1000, "unit": "g", "unit_price": 0.00189, "confidence": 0.96},
        {"name": "tinned tomatoes", "quantity": 4, "unit": "units", "unit_price": 0.50, "confidence": 0.85}
      ]
    }
  },
  {
    "input": {
      "line_items": [
        {"name": "SALMON FILLETS 2PK 260G", "quantity_raw": "1", "price": "5.00"}
      ]
    },
    "expected": {
      "items": [
        {"name": "salmon fillet", "quantity": 260, "unit": "g", "unit_price": 0.01923, "confidence": 0.90}
      ]
    }
  }
]
```

- [ ] **Step 3: Create suggestions golden dataset**

Create `backend/tests/evals/fixtures/suggestions.json`:

```json
[
  {
    "input": {
      "pantry": [
        {"id": 1, "name": "chicken breast", "quantity": 400, "unit": "g", "food_group": "protein", "urgency_score": 85.0},
        {"id": 2, "name": "broccoli", "quantity": 300, "unit": "g", "food_group": "veg", "urgency_score": 72.0},
        {"id": 3, "name": "basmati rice", "quantity": 800, "unit": "g", "food_group": "carb", "urgency_score": 10.0}
      ],
      "recipe_history": [
        {"recipe_id": 1, "title": "Chicken Stir Fry", "last_cooked_at": "2026-03-17T00:00:00Z", "food_groups": ["protein", "veg"]},
        {"recipe_id": 2, "title": "Chicken Curry", "last_cooked_at": "2026-04-01T00:00:00Z", "food_groups": ["protein", "carb"]},
        {"recipe_id": 3, "title": "Lentil Soup", "last_cooked_at": null, "food_groups": ["protein", "carb"]}
      ],
      "food_group_coverage": {"protein": 1, "carb": 2, "veg": 0},
      "purchase_tolerance": 0.3,
      "meals_per_week": 3,
      "dietary_flags": [],
      "max_active_time_mins": null
    },
    "expected": {
      "suggestions": [
        {
          "recipe_id": 1,
          "title": "Chicken Stir Fry",
          "reason": "Uses chicken breast (urgency 85, expiring soon) and broccoli (urgency 72). Covers protein and veg — veg has 0 coverage this week. Not cooked since March 17.",
          "missing_ingredients": ["soy sauce"]
        },
        {
          "recipe_id": 3,
          "title": "Lentil Soup",
          "reason": "Never cooked before. Covers protein and carb food groups. No missing ingredients needed.",
          "missing_ingredients": []
        }
      ]
    }
  },
  {
    "input": {
      "pantry": [
        {"id": 4, "name": "salmon fillet", "quantity": 260, "unit": "g", "food_group": "protein", "urgency_score": 95.0},
        {"id": 5, "name": "lemon", "quantity": 2, "unit": "units", "food_group": "fruit", "urgency_score": 60.0},
        {"id": 6, "name": "asparagus", "quantity": 200, "unit": "g", "food_group": "veg", "urgency_score": 88.0}
      ],
      "recipe_history": [
        {"recipe_id": 10, "title": "Lemon Salmon", "last_cooked_at": "2026-03-01T00:00:00Z", "food_groups": ["protein", "veg"]},
        {"recipe_id": 11, "title": "Pasta Carbonara", "last_cooked_at": "2026-04-05T00:00:00Z", "food_groups": ["protein", "carb"]}
      ],
      "food_group_coverage": {"protein": 0, "carb": 1, "veg": 0},
      "purchase_tolerance": 0.0,
      "meals_per_week": 2,
      "dietary_flags": ["pescatarian"],
      "max_active_time_mins": 30
    },
    "expected": {
      "suggestions": [
        {
          "recipe_id": 10,
          "title": "Lemon Salmon",
          "reason": "Uses salmon (urgency 95) and lemon (urgency 60). Covers protein and veg, both at 0 this week. Pescatarian-friendly.",
          "missing_ingredients": []
        }
      ]
    }
  },
  {
    "input": {
      "pantry": [
        {"id": 7, "name": "tofu", "quantity": 400, "unit": "g", "food_group": "protein", "urgency_score": 45.0},
        {"id": 8, "name": "spinach", "quantity": 150, "unit": "g", "food_group": "veg", "urgency_score": 92.0}
      ],
      "recipe_history": [
        {"recipe_id": 20, "title": "Tofu Stir Fry", "last_cooked_at": "2026-04-07T00:00:00Z", "food_groups": ["protein", "veg"]},
        {"recipe_id": 21, "title": "Steak and Chips", "last_cooked_at": null, "food_groups": ["protein", "carb"]}
      ],
      "food_group_coverage": {"protein": 3, "carb": 2, "veg": 1},
      "purchase_tolerance": 0.5,
      "meals_per_week": 2,
      "dietary_flags": ["vegan"],
      "max_active_time_mins": null
    },
    "expected": {
      "suggestions": [
        {
          "recipe_id": 20,
          "title": "Tofu Stir Fry",
          "reason": "Uses spinach (urgency 92, expiring soon) and tofu. Vegan-friendly. Cooked recently but spinach urgency overrides.",
          "missing_ingredients": []
        }
      ]
    }
  }
]
```

- [ ] **Step 4: Create recipe_import golden dataset**

Create `backend/tests/evals/fixtures/recipe_import.json`:

```json
[
  {
    "input": {
      "html": "<html><head><title>Classic Spaghetti Carbonara</title></head><body><h1>Classic Spaghetti Carbonara</h1><p>A traditional Italian pasta dish.</p><h2>Ingredients</h2><ul><li>400g spaghetti</li><li>200g guanciale or pancetta</li><li>4 large egg yolks</li><li>100g pecorino romano</li><li>Freshly ground black pepper</li></ul><h2>Method</h2><ol><li>Cook the spaghetti in salted boiling water until al dente.</li><li>Meanwhile, cut the guanciale into small strips and fry until crispy.</li><li>Beat the egg yolks with grated pecorino and black pepper.</li><li>Drain pasta, reserving some cooking water. Toss with guanciale off heat.</li><li>Add egg mixture, toss quickly. Add cooking water if needed for creaminess.</li></ol><p>Serves 4. Total time: 25 minutes.</p></body></html>",
      "url": "https://example.com/carbonara"
    },
    "expected": {
      "title": "Classic Spaghetti Carbonara",
      "source_url": "https://example.com/carbonara",
      "ingredients": ["400g spaghetti", "200g guanciale or pancetta", "4 large egg yolks", "100g pecorino romano", "Freshly ground black pepper"],
      "instructions": [
        "Cook the spaghetti in salted boiling water until al dente.",
        "Meanwhile, cut the guanciale into small strips and fry until crispy.",
        "Beat the egg yolks with grated pecorino and black pepper.",
        "Drain pasta, reserving some cooking water. Toss with guanciale off heat.",
        "Add egg mixture, toss quickly. Add cooking water if needed for creaminess."
      ],
      "total_time": "PT25M"
    }
  },
  {
    "input": {
      "html": "<html><body><h1>Simple Tomato Soup</h1><p>Prep: 10 mins | Cook: 30 mins</p><h3>What you need</h3><p>2 tins chopped tomatoes, 1 onion, 2 cloves garlic, 500ml vegetable stock, 1 tbsp olive oil, salt and pepper</p><h3>How to make it</h3><p>1. Dice the onion and garlic. Heat oil in a large saucepan. 2. Fry onion until soft, add garlic for 1 minute. 3. Add tomatoes and stock, bring to a boil. 4. Simmer for 25 minutes. 5. Blend until smooth and season to taste.</p><p>Makes 4 bowls.</p></body></html>",
      "url": "https://example.com/tomato-soup"
    },
    "expected": {
      "title": "Simple Tomato Soup",
      "source_url": "https://example.com/tomato-soup",
      "ingredients": ["2 tins chopped tomatoes", "1 onion", "2 cloves garlic", "500ml vegetable stock", "1 tbsp olive oil", "salt and pepper"],
      "instructions": [
        "Dice the onion and garlic. Heat oil in a large saucepan.",
        "Fry onion until soft, add garlic for 1 minute.",
        "Add tomatoes and stock, bring to a boil.",
        "Simmer for 25 minutes.",
        "Blend until smooth and season to taste."
      ],
      "total_time": "PT40M"
    }
  },
  {
    "input": {
      "html": "<html><body><article><h1>Vegan Thai Green Curry</h1><div class='meta'>Difficulty: Easy | Time: 35 minutes | Serves 4</div><div class='ingredients'><h2>Ingredients</h2><ul><li>1 tin coconut milk</li><li>2 tbsp green curry paste</li><li>200g tofu, cubed</li><li>1 red pepper, sliced</li><li>100g baby sweetcorn</li><li>Handful of Thai basil</li><li>1 tbsp soy sauce</li><li>Jasmine rice to serve</li></ul></div><div class='method'><h2>Method</h2><ol><li>Heat a splash of coconut milk in a wok until bubbling.</li><li>Fry the curry paste for 2 minutes until fragrant.</li><li>Add remaining coconut milk, tofu, pepper and sweetcorn.</li><li>Simmer for 15 minutes until vegetables are tender.</li><li>Stir in soy sauce and Thai basil. Serve over jasmine rice.</li></ol></div></article></body></html>",
      "url": "https://example.com/thai-green-curry"
    },
    "expected": {
      "title": "Vegan Thai Green Curry",
      "source_url": "https://example.com/thai-green-curry",
      "ingredients": ["1 tin coconut milk", "2 tbsp green curry paste", "200g tofu, cubed", "1 red pepper, sliced", "100g baby sweetcorn", "Handful of Thai basil", "1 tbsp soy sauce", "Jasmine rice to serve"],
      "instructions": [
        "Heat a splash of coconut milk in a wok until bubbling.",
        "Fry the curry paste for 2 minutes until fragrant.",
        "Add remaining coconut milk, tofu, pepper and sweetcorn.",
        "Simmer for 15 minutes until vegetables are tender.",
        "Stir in soy sauce and Thai basil. Serve over jasmine rice."
      ],
      "dietary_flags": ["vegan"],
      "total_time": "PT35M"
    }
  }
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/
git commit -m "📦 feat: add golden eval datasets for all three Claude features"
```

---

### Task 6: Create eval conftest and LLM-as-judge rubrics

**Files:**
- Create: `backend/tests/evals/conftest.py`
- Create: `backend/tests/evals/judges/__init__.py`
- Create: `backend/tests/evals/judges/rubrics.py`

- [ ] **Step 1: Create eval conftest with dataset loading fixtures**

Create `backend/tests/evals/conftest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel

from glean.llm import create_chat_model

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="session")
def eval_model() -> BaseChatModel:
    """Create the LLM used for eval runs. Configured via env vars."""
    import os

    provider = os.environ.get("GLEAN_LLM_PROVIDER", "anthropic")
    model = os.environ.get("GLEAN_LLM_MODEL", "claude-sonnet-4-6")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    return create_chat_model(provider, model, api_key=api_key)


@pytest.fixture(scope="session")
def judge_model() -> BaseChatModel:
    """Create the LLM used for LLM-as-judge scoring. Same model as eval_model."""
    import os

    provider = os.environ.get("GLEAN_LLM_PROVIDER", "anthropic")
    model = os.environ.get("GLEAN_LLM_MODEL", "claude-sonnet-4-6")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    return create_chat_model(provider, model, api_key=api_key)


@pytest.fixture(scope="session")
def receipt_scan_dataset() -> list[dict[str, Any]]:
    return _load_fixture("receipt_scan.json")


@pytest.fixture(scope="session")
def suggestions_dataset() -> list[dict[str, Any]]:
    return _load_fixture("suggestions.json")


@pytest.fixture(scope="session")
def recipe_import_dataset() -> list[dict[str, Any]]:
    return _load_fixture("recipe_import.json")
```

- [ ] **Step 2: Create judge package**

Create empty `backend/tests/evals/judges/__init__.py`.

- [ ] **Step 3: Create LLM-as-judge rubrics module**

Create `backend/tests/evals/judges/rubrics.py`:

```python
from __future__ import annotations

import json
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

RECEIPT_SCAN_RUBRIC = """You are evaluating a grocery receipt normalisation system.
Given a raw receipt line item name and the system's normalised output, rate the quality 1-5:

5 = Perfect canonical name, correct unit conversion, accurate price calculation
4 = Minor issue (slightly verbose name, small rounding difference)
3 = Acceptable but imprecise (name has extra words, unit roughly correct)
2 = Significant error (wrong unit type, major quantity error)
1 = Wrong (completely misidentified item)

Respond with ONLY a single integer 1-5. No explanation."""

SUGGESTIONS_RUBRIC = """You are evaluating a meal suggestion system.
Given a user's pantry state, dietary flags, and the system's suggestion, rate the quality 1-5:

5 = Excellent — uses expiring/urgent pantry items, reason is specific and references actual pantry data
4 = Good — reasonable suggestion, reason references pantry items by name
3 = Acceptable — valid recipe but reason is generic (e.g. "good for dinner")
2 = Poor — ignores pantry priorities or reason is vague/irrelevant
1 = Bad — violates dietary flags or completely irrelevant to pantry state

Respond with ONLY a single integer 1-5. No explanation."""

RECIPE_IMPORT_RUBRIC = """You are evaluating a recipe extraction system.
Given source HTML and the system's extracted recipe JSON, rate the extraction quality 1-5:

5 = Perfect — all fields accurately captured from the HTML
4 = Minor omission (missing optional field like cuisine or difficulty)
3 = Mostly correct but missing some ingredients or instruction steps
2 = Significant errors (wrong title, missing most ingredients)
1 = Completely wrong extraction

Respond with ONLY a single integer 1-5. No explanation."""


def _parse_score(content: str) -> int:
    """Extract integer score from LLM response, defaulting to 1 if unparseable."""
    match = re.search(r"[1-5]", content)
    return int(match.group()) if match else 1


def judge_receipt_scan(
    model: BaseChatModel,
    raw_name: str,
    normalised_name: str,
    quantity: float,
    unit: str,
    unit_price: float | None,
) -> int:
    prompt = (
        f'Raw receipt item: "{raw_name}"\n'
        f'Normalised to: "{normalised_name}", quantity={quantity}{unit}, unit_price={unit_price}/{unit}'
    )
    result = model.invoke(
        [SystemMessage(content=RECEIPT_SCAN_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-receipt"}},
    )
    return _parse_score(result.content)


def judge_suggestion(
    model: BaseChatModel,
    pantry_summary: str,
    dietary_flags: list[str],
    title: str,
    reason: str,
) -> int:
    prompt = (
        f"Pantry state:\n{pantry_summary}\n\n"
        f"Dietary flags: {dietary_flags}\n\n"
        f'Suggested recipe: "{title}"\n'
        f'Reason: "{reason}"'
    )
    result = model.invoke(
        [SystemMessage(content=SUGGESTIONS_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-suggestions"}},
    )
    return _parse_score(result.content)


def judge_recipe_import(
    model: BaseChatModel,
    html_snippet: str,
    extracted_json: dict,
) -> int:
    prompt = (
        f"Source HTML (first 2000 chars):\n{html_snippet[:2000]}\n\n"
        f"Extracted recipe:\n{json.dumps(extracted_json, indent=2)}"
    )
    result = model.invoke(
        [SystemMessage(content=RECIPE_IMPORT_RUBRIC), HumanMessage(content=prompt)],
        config={"metadata": {"feature": "eval-judge-recipe-import"}},
    )
    return _parse_score(result.content)
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/evals/conftest.py backend/tests/evals/judges/
git commit -m "🧪 feat: add eval conftest fixtures and LLM-as-judge rubrics"
```

---

### Task 7: Create receipt scan eval suite

**Files:**
- Create: `backend/tests/evals/test_receipt_scan.py`

- [ ] **Step 1: Write the receipt scan eval test file**

Create `backend/tests/evals/test_receipt_scan.py`:

```python
from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from glean.receipts.schemas import ParsedIngredient
from glean.receipts.service import NORMALISE_SYSTEM_PROMPT

from .judges.rubrics import judge_receipt_scan

ALLOWED_UNITS = {"g", "ml", "units"}


class TestReceiptScanStructural:
    """Layer 1: Structural checks (hard gate). JSON + schema validation."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            raw = json.loads(result.content)
            assert isinstance(raw, list), f"Example {i}: expected list, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            raw = json.loads(result.content)
            items = [ParsedIngredient(**item) for item in raw]
            assert len(items) > 0, f"Example {i}: returned empty list"

    def test_all_items_have_valid_units(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for item in items:
                assert item.unit in ALLOWED_UNITS, (
                    f"Example {i}: item '{item.name}' has unit '{item.unit}', expected one of {ALLOWED_UNITS}"
                )

    def test_output_count_matches_input_count(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = json.loads(result.content)
            expected_count = len(example["input"]["line_items"])
            assert len(items) == expected_count, (
                f"Example {i}: expected {expected_count} items, got {len(items)}"
            )


@pytest.mark.soft_gate
class TestReceiptScanHeuristic:
    """Layer 2: Heuristic checks (soft gate). Deterministic quality checks."""

    def test_names_are_lowercase(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for item in items:
                if item.name != item.name.lower():
                    failures.append(f"Example {i}: '{item.name}' is not lowercase")
        assert not failures, f"Lowercase check failures:\n" + "\n".join(failures)

    def test_no_common_abbreviations(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        abbreviations = {"bnls", "chkn", "whl", "org", "brst", "flts", "sml", "lrg", "med", "pck"}
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for item in items:
                words = set(item.name.lower().split())
                found = words & abbreviations
                if found:
                    failures.append(f"Example {i}: '{item.name}' contains abbreviations: {found}")
        assert not failures, f"Abbreviation check failures:\n" + "\n".join(failures)

    def test_quantities_are_positive(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for item in items:
                if item.quantity <= 0:
                    failures.append(f"Example {i}: '{item.name}' has quantity {item.quantity}")
                if item.unit_price is not None and item.unit_price <= 0:
                    failures.append(f"Example {i}: '{item.name}' has unit_price {item.unit_price}")
        assert not failures, f"Positive quantity check failures:\n" + "\n".join(failures)

    def test_confidence_in_range(
        self,
        eval_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for item in items:
                if not (0.0 <= item.confidence <= 1.0):
                    failures.append(f"Example {i}: '{item.name}' has confidence {item.confidence}")
        assert not failures, f"Confidence range check failures:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestReceiptScanJudge:
    """Layer 3: LLM-as-judge (soft gate). Quality scoring via rubric."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        receipt_scan_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(receipt_scan_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=NORMALISE_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(example["input"]["line_items"])),
                ],
                config={"metadata": {"feature": "eval-receipt-scan", "example_idx": i}},
            )
            items = [ParsedIngredient(**item) for item in json.loads(result.content)]
            for j, (item, raw_input) in enumerate(zip(items, example["input"]["line_items"])):
                score = judge_receipt_scan(
                    model=judge_model,
                    raw_name=raw_input["name"],
                    normalised_name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    unit_price=item.unit_price,
                )
                scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `cd backend && uv run python -c "import ast; ast.parse(open('tests/evals/test_receipt_scan.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/evals/test_receipt_scan.py
git commit -m "🧪 feat: add receipt scan eval suite (structural, heuristic, judge)"
```

---

### Task 8: Create suggestions eval suite

**Files:**
- Create: `backend/tests/evals/test_suggestions.py`

- [ ] **Step 1: Write the suggestions eval test file**

Create `backend/tests/evals/test_suggestions.py`:

```python
from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from glean.suggestions.schemas import SuggestedRecipe
from glean.suggestions.service import SUGGESTION_SYSTEM_PROMPT

from .judges.rubrics import judge_suggestion


class TestSuggestionsStructural:
    """Layer 1: Structural checks (hard gate)."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            raw = json.loads(result.content)
            assert isinstance(raw, list), f"Example {i}: expected list, got {type(raw).__name__}"

    def test_all_examples_conform_to_schema(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            raw = json.loads(result.content)
            suggestions = [SuggestedRecipe(**item) for item in raw]
            assert len(suggestions) > 0, f"Example {i}: returned empty list"

    def test_suggestion_count_within_limit(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            suggestions = json.loads(result.content)
            limit = example["input"]["meals_per_week"]
            assert len(suggestions) <= limit, (
                f"Example {i}: got {len(suggestions)} suggestions, limit is {limit}"
            )

    def test_recipe_ids_are_integers(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(suggestions_dataset):
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            for item in json.loads(result.content):
                assert isinstance(item["recipe_id"], int), (
                    f"Example {i}: recipe_id {item['recipe_id']} is not an int"
                )


@pytest.mark.soft_gate
class TestSuggestionsHeuristic:
    """Layer 2: Heuristic checks (soft gate)."""

    def test_missing_ingredients_not_in_pantry(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            pantry_names = {item["name"].lower() for item in example["input"]["pantry"]}
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            suggestions = [SuggestedRecipe(**item) for item in json.loads(result.content)]
            for s in suggestions:
                overlap = {ing.lower() for ing in s.missing_ingredients} & pantry_names
                if overlap:
                    failures.append(
                        f"Example {i}: '{s.title}' lists {overlap} as missing but they're in pantry"
                    )
        assert not failures, f"Missing ingredients check:\n" + "\n".join(failures)

    def test_recipe_ids_reference_known_recipes(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            known_ids = {r["recipe_id"] for r in example["input"]["recipe_history"]}
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            suggestions = [SuggestedRecipe(**item) for item in json.loads(result.content)]
            for s in suggestions:
                if s.recipe_id not in known_ids:
                    failures.append(
                        f"Example {i}: recipe_id {s.recipe_id} ('{s.title}') not in input history {known_ids}"
                    )
        assert not failures, f"Recipe ID reference check:\n" + "\n".join(failures)

    def test_reasons_are_substantive(
        self,
        eval_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(suggestions_dataset):
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            suggestions = [SuggestedRecipe(**item) for item in json.loads(result.content)]
            for s in suggestions:
                if len(s.reason) < 10:
                    failures.append(
                        f"Example {i}: '{s.title}' reason too short ({len(s.reason)} chars): '{s.reason}'"
                    )
        assert not failures, f"Reason length check:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestSuggestionsJudge:
    """Layer 3: LLM-as-judge (soft gate)."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        suggestions_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(suggestions_dataset):
            pantry_summary = "\n".join(
                f"- {p['name']}: {p['quantity']}{p['unit']} (urgency: {p['urgency_score']})"
                for p in example["input"]["pantry"]
            )
            context = json.dumps(example["input"], default=str)
            result = eval_model.invoke(
                [
                    SystemMessage(content=SUGGESTION_SYSTEM_PROMPT),
                    HumanMessage(content=context),
                ],
                config={"metadata": {"feature": "eval-suggestions", "example_idx": i}},
            )
            suggestions = [SuggestedRecipe(**item) for item in json.loads(result.content)]
            for s in suggestions:
                score = judge_suggestion(
                    model=judge_model,
                    pantry_summary=pantry_summary,
                    dietary_flags=example["input"]["dietary_flags"],
                    title=s.title,
                    reason=s.reason,
                )
                scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `cd backend && uv run python -c "import ast; ast.parse(open('tests/evals/test_suggestions.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/evals/test_suggestions.py
git commit -m "🧪 feat: add suggestions eval suite (structural, heuristic, judge)"
```

---

### Task 9: Create recipe import eval suite

**Files:**
- Create: `backend/tests/evals/test_recipe_import.py`

- [ ] **Step 1: Write the recipe import eval test file**

Create `backend/tests/evals/test_recipe_import.py`:

```python
from __future__ import annotations

import json
import re
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from glean.recipes.service import URL_PARSE_SYSTEM_PROMPT

from .judges.rubrics import judge_recipe_import


class TestRecipeImportStructural:
    """Layer 1: Structural checks (hard gate)."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            assert isinstance(raw, dict), f"Example {i}: expected dict, got {type(raw).__name__}"

    def test_all_examples_have_required_fields(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        required_fields = {"title", "ingredients", "instructions"}
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            missing = required_fields - set(raw.keys())
            assert not missing, f"Example {i}: missing required fields: {missing}"

    def test_ingredients_and_instructions_are_lists(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            assert isinstance(raw["ingredients"], list), f"Example {i}: ingredients is not a list"
            assert isinstance(raw["instructions"], list), f"Example {i}: instructions is not a list"
            assert len(raw["ingredients"]) > 0, f"Example {i}: ingredients list is empty"
            assert len(raw["instructions"]) >= 2, (
                f"Example {i}: instructions has {len(raw['instructions'])} steps, expected >= 2"
            )

    def test_title_is_nonempty_string(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            assert isinstance(raw["title"], str), f"Example {i}: title is not a string"
            assert len(raw["title"].strip()) > 0, f"Example {i}: title is empty"


@pytest.mark.soft_gate
class TestRecipeImportHeuristic:
    """Layer 2: Heuristic checks (soft gate)."""

    def test_no_empty_instruction_steps(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            for j, step in enumerate(raw.get("instructions", [])):
                if not step or not step.strip():
                    failures.append(f"Example {i}: instruction step {j + 1} is empty")
        assert not failures, f"Empty instruction check:\n" + "\n".join(failures)

    def test_total_time_is_valid_iso8601(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        iso_pattern = re.compile(r"^PT(\d+H)?(\d+M)?(\d+S)?$")
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            total_time = raw.get("total_time")
            if total_time and not iso_pattern.match(total_time):
                failures.append(f"Example {i}: total_time '{total_time}' is not valid ISO 8601 duration")
        assert not failures, f"ISO 8601 duration check:\n" + "\n".join(failures)

    def test_no_empty_ingredients(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            for j, ing in enumerate(raw.get("ingredients", [])):
                if not ing or not ing.strip():
                    failures.append(f"Example {i}: ingredient {j + 1} is empty")
        assert not failures, f"Empty ingredient check:\n" + "\n".join(failures)

    def test_dietary_flags_are_strings(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            for flag in raw.get("dietary_flags", []):
                if not isinstance(flag, str):
                    failures.append(f"Example {i}: dietary_flag {flag} is not a string")
        assert not failures, f"Dietary flags type check:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestRecipeImportJudge:
    """Layer 3: LLM-as-judge (soft gate)."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(recipe_import_dataset):
            result = eval_model.invoke(
                [
                    SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
                    HumanMessage(content=f"Parse this HTML:\n\n{example['input']['html'][:8000]}"),
                ],
                config={"metadata": {"feature": "eval-recipe-import", "example_idx": i}},
            )
            raw = json.loads(result.content)
            score = judge_recipe_import(
                model=judge_model,
                html_snippet=example["input"]["html"],
                extracted_json=raw,
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `cd backend && uv run python -c "import ast; ast.parse(open('tests/evals/test_recipe_import.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/evals/test_recipe_import.py
git commit -m "🧪 feat: add recipe import eval suite (structural, heuristic, judge)"
```

---

### Task 10: Create GitHub Actions eval workflow

**Files:**
- Create: `.github/workflows/llm-evals.yml`

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/llm-evals.yml`:

```yaml
name: LLM Evals

on:
  workflow_dispatch:
    inputs:
      provider:
        description: 'LLM provider (anthropic or google)'
        required: true
        default: 'google'
        type: choice
        options:
          - anthropic
          - google
      model:
        description: 'Model name'
        required: true
        default: 'gemma-3'
        type: string

permissions:
  contents: read
  pull-requests: write

jobs:
  eval:
    name: Run Evals
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    env:
      GLEAN_LLM_PROVIDER: ${{ inputs.provider }}
      GLEAN_LLM_MODEL: ${{ inputs.model }}
      LANGCHAIN_TRACING_V2: "true"
      LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
      LANGCHAIN_PROJECT: glean-evals
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.14"

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Run structural evals (hard gate)
        id: hard_gate
        run: |
          uv run pytest tests/evals/ -m "not soft_gate" -v --tb=short --no-cov \
            --junitxml=results/hard-gate.xml 2>&1 | tee results/hard-gate.txt
        continue-on-error: true

      - name: Run heuristic + judge evals (soft gate)
        id: soft_gate
        run: |
          uv run pytest tests/evals/ -m "soft_gate" -v --tb=short --no-cov \
            --junitxml=results/soft-gate.xml 2>&1 | tee results/soft-gate.txt
        continue-on-error: true

      - name: Generate PR comment
        if: always()
        run: |
          python ../scripts/generate_eval_comment.py \
            --hard-gate results/hard-gate.xml \
            --soft-gate results/soft-gate.xml \
            --model "${{ inputs.provider }}/${{ inputs.model }}" \
            > results/pr-comment.md

      - name: Post PR comment
        if: always() && github.event_name == 'workflow_dispatch'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          PR_NUMBER=$(gh pr list --head "${{ github.ref_name }}" --json number -q '.[0].number')
          if [ -n "$PR_NUMBER" ]; then
            gh pr comment "$PR_NUMBER" --body-file results/pr-comment.md
          else
            echo "No PR found for branch ${{ github.ref_name }}, skipping comment"
          fi

      - name: Fail if hard gate failed
        if: steps.hard_gate.outcome == 'failure'
        run: exit 1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/llm-evals.yml
git commit -m "🔄 ci: add manual LLM eval workflow with tiered gating"
```

---

### Task 11: Create PR comment generator script

**Files:**
- Create: `backend/scripts/generate_eval_comment.py`

- [ ] **Step 1: Write the comment generator**

Create `backend/scripts/generate_eval_comment.py`:

```python
#!/usr/bin/env python3
"""Generate a jazzy GitHub PR comment from eval JUnit XML results."""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class TestResult:
    name: str
    classname: str
    passed: bool
    failure_message: str = ""


@dataclass
class FeatureResults:
    structural: list[TestResult] = field(default_factory=list)
    heuristic: list[TestResult] = field(default_factory=list)
    judge: list[TestResult] = field(default_factory=list)


def parse_junit_xml(path: str) -> list[TestResult]:
    results: list[TestResult] = []
    try:
        tree = ET.parse(path)
    except (ET.ParseError, FileNotFoundError):
        return results
    for testcase in tree.iter("testcase"):
        failure = testcase.find("failure")
        results.append(
            TestResult(
                name=testcase.get("name", ""),
                classname=testcase.get("classname", ""),
                passed=failure is None,
                failure_message=failure.get("message", "") if failure is not None else "",
            )
        )
    return results


def classify_results(results: list[TestResult]) -> dict[str, FeatureResults]:
    features: dict[str, FeatureResults] = {
        "receipt-scan": FeatureResults(),
        "suggestions": FeatureResults(),
        "recipe-import": FeatureResults(),
    }
    for r in results:
        classname_lower = r.classname.lower()
        if "receipt" in classname_lower:
            feature = "receipt-scan"
        elif "suggestion" in classname_lower:
            feature = "suggestions"
        elif "recipe" in classname_lower:
            feature = "recipe-import"
        else:
            continue

        if "structural" in classname_lower:
            features[feature].structural.append(r)
        elif "heuristic" in classname_lower:
            features[feature].heuristic.append(r)
        elif "judge" in classname_lower:
            features[feature].judge.append(r)
    return features


def _score(results: list[TestResult]) -> str:
    if not results:
        return "—"
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    return f"{passed}/{total}"


def _pct(results: list[TestResult]) -> str:
    if not results:
        return "—"
    passed = sum(1 for r in results if r.passed)
    return f"{100 * passed // len(results)}%"


def _status_icon(results: list[TestResult]) -> str:
    if not results:
        return "⬜"
    return "✅" if all(r.passed for r in results) else "❌"


def _detail_section(name: str, fr: FeatureResults) -> str:
    structural_score = _score(fr.structural)
    heuristic_score = _pct(fr.heuristic)
    judge_score = _pct(fr.judge)

    lines = [
        f"<details>",
        f"<summary><strong>{name}</strong> — {structural_score} structural, {heuristic_score} heuristic, {judge_score} judge</summary>",
        "",
        "### Structural (hard gate)",
    ]

    if fr.structural:
        if all(r.passed for r in fr.structural):
            lines.append(f"All {len(fr.structural)} checks passed.")
        else:
            lines.append("")
            lines.append("| Check | Status |")
            lines.append("|-------|--------|")
            for r in fr.structural:
                icon = "✅" if r.passed else "❌"
                lines.append(f"| {r.name} | {icon} |")
            failures = [r for r in fr.structural if not r.passed]
            if failures:
                lines.append("")
                lines.append("**Failures:**")
                for r in failures:
                    lines.append(f"- `{r.name}`: {r.failure_message}")
    else:
        lines.append("No structural tests found.")

    lines.extend(["", "### Heuristic (soft gate)"])
    if fr.heuristic:
        lines.append("")
        lines.append("| Check | Status |")
        lines.append("|-------|--------|")
        for r in fr.heuristic:
            icon = "✅" if r.passed else "⚠️"
            lines.append(f"| {r.name} | {icon} |")
        failures = [r for r in fr.heuristic if not r.passed]
        if failures:
            lines.append("")
            lines.append("**Issues:**")
            for r in failures:
                lines.append(f"- `{r.name}`: {r.failure_message}")
    else:
        lines.append("No heuristic tests found.")

    lines.extend(["", "### LLM Judge (soft gate)"])
    if fr.judge:
        for r in fr.judge:
            icon = "✅" if r.passed else "⚠️"
            lines.append(f"- {icon} {r.name}")
            if not r.passed:
                lines.append(f"  - {r.failure_message}")
    else:
        lines.append("No judge tests found.")

    lines.extend(["", "</details>", ""])
    return "\n".join(lines)


def generate_comment(
    hard_results: list[TestResult],
    soft_results: list[TestResult],
    model: str,
) -> str:
    all_results = hard_results + soft_results
    features = classify_results(all_results)

    hard_passed = all(r.passed for r in hard_results) if hard_results else True
    soft_issues = [r for r in soft_results if not r.passed]

    lines = [
        f"## 🧪 Eval Results — `{model}`",
        "",
        "| Feature | Structural | Heuristic | LLM Judge |",
        "|---------|:----------:|:---------:|:---------:|",
    ]

    for name, fr in features.items():
        s_icon = _status_icon(fr.structural)
        lines.append(
            f"| {name} | {s_icon} {_score(fr.structural)} | {_pct(fr.heuristic)} | {_pct(fr.judge)} |"
        )

    lines.append("")
    if hard_passed:
        lines.append("**Hard gate:** ✅ Passed — all structural checks passed")
    else:
        lines.append("**Hard gate:** ❌ Failed — structural checks have failures")

    if soft_issues:
        lines.append(f"**Soft gate:** ⚠️ Advisory — {len(soft_issues)} soft check(s) flagged")
    else:
        lines.append("**Soft gate:** ✅ All soft checks passed")

    lines.append("")
    lines.append("---")
    lines.append("")

    for name, fr in features.items():
        lines.append(_detail_section(name, fr))

    lines.append("---")
    lines.append("")
    lines.append("🔗 View traces in LangSmith: `glean-evals` project")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate eval PR comment from JUnit XML")
    parser.add_argument("--hard-gate", required=True, help="Path to hard-gate JUnit XML")
    parser.add_argument("--soft-gate", required=True, help="Path to soft-gate JUnit XML")
    parser.add_argument("--model", required=True, help="Model identifier for display")
    args = parser.parse_args()

    hard_results = parse_junit_xml(args.hard_gate)
    soft_results = parse_junit_xml(args.soft_gate)
    comment = generate_comment(hard_results, soft_results, args.model)
    sys.stdout.write(comment)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write a test for the comment generator**

Create `backend/tests/test_generate_eval_comment.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is not a package — add it to sys.path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_eval_comment import TestResult, classify_results, generate_comment


class TestGenerateEvalComment:
    def test_classify_receipt_structural(self) -> None:
        results = [
            TestResult(
                name="test_valid_json",
                classname="tests.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=True,
            ),
        ]
        features = classify_results(results)
        assert len(features["receipt-scan"].structural) == 1
        assert features["receipt-scan"].structural[0].passed

    def test_classify_suggestions_heuristic(self) -> None:
        results = [
            TestResult(
                name="test_missing_ingredients_not_in_pantry",
                classname="tests.evals.test_suggestions.TestSuggestionsHeuristic",
                passed=False,
                failure_message="rice was in pantry",
            ),
        ]
        features = classify_results(results)
        assert len(features["suggestions"].heuristic) == 1
        assert not features["suggestions"].heuristic[0].passed

    def test_generate_comment_has_summary_table(self) -> None:
        hard = [
            TestResult(
                name="test_valid_json",
                classname="tests.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=True,
            ),
        ]
        soft = [
            TestResult(
                name="test_names_lowercase",
                classname="tests.evals.test_receipt_scan.TestReceiptScanHeuristic",
                passed=True,
            ),
        ]
        comment = generate_comment(hard, soft, "google/gemma-3")
        assert "## 🧪 Eval Results — `google/gemma-3`" in comment
        assert "| receipt-scan" in comment
        assert "Hard gate:" in comment

    def test_generate_comment_hard_gate_failure(self) -> None:
        hard = [
            TestResult(
                name="test_valid_json",
                classname="tests.evals.test_receipt_scan.TestReceiptScanStructural",
                passed=False,
                failure_message="Expected list, got str",
            ),
        ]
        comment = generate_comment(hard, [], "google/gemma-3")
        assert "❌ Failed" in comment
```

- [ ] **Step 3: Run the test**

Run: `cd backend && uv run pytest tests/test_generate_eval_comment.py -v`
Expected: All 4 tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/generate_eval_comment.py backend/tests/test_generate_eval_comment.py
git commit -m "📊 feat: add PR comment generator for eval results"
```

---

### Task 12: Create LangSmith dataset sync script

**Files:**
- Create: `backend/scripts/sync_eval_datasets.py`

- [ ] **Step 1: Write the sync script**

Create `backend/scripts/sync_eval_datasets.py`:

```python
#!/usr/bin/env python3
"""Push local eval fixture files to LangSmith datasets (one-way: git → LangSmith)."""
from __future__ import annotations

import json
from pathlib import Path

from langsmith import Client

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "evals" / "fixtures"

DATASETS = {
    "receipt_scan.json": "glean-receipt-scan",
    "suggestions.json": "glean-suggestions",
    "recipe_import.json": "glean-recipe-import",
}


def sync_dataset(client: Client, fixture_path: Path, dataset_name: str) -> None:
    examples = json.loads(fixture_path.read_text())

    # Delete existing dataset if it exists, then recreate
    try:
        existing = client.read_dataset(dataset_name=dataset_name)
        client.delete_dataset(dataset_id=existing.id)
        print(f"  Deleted existing dataset: {dataset_name}")
    except Exception:  # noqa: BLE001
        pass

    dataset = client.create_dataset(dataset_name=dataset_name)
    print(f"  Created dataset: {dataset_name}")

    for i, example in enumerate(examples):
        client.create_example(
            inputs=example["input"],
            outputs=example.get("expected", {}),
            dataset_id=dataset.id,
        )
    print(f"  Uploaded {len(examples)} examples")


def main() -> None:
    client = Client()
    print("Syncing eval datasets to LangSmith...")
    for filename, dataset_name in DATASETS.items():
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            print(f"  Skipping {filename}: file not found")
            continue
        print(f"\n{filename} → {dataset_name}")
        sync_dataset(client, fixture_path, dataset_name)
    print("\nDone.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add backend/scripts/sync_eval_datasets.py
git commit -m "🔄 feat: add one-way dataset sync script (git → LangSmith)"
```

---

### Task 13: Create results output directory and update .gitignore

**Files:**
- Modify: `backend/.gitignore` (or create if needed)

- [ ] **Step 1: Ensure results directory is gitignored**

Add to `backend/.gitignore` (create if it doesn't exist):

```
# Eval results (generated by CI)
results/
```

- [ ] **Step 2: Add mkdir to the CI workflow**

In `.github/workflows/llm-evals.yml`, add a step before the hard gate step:

```yaml
      - name: Create results directory
        run: mkdir -p results
```

This goes after "Install dependencies" and before "Run structural evals".

- [ ] **Step 3: Commit**

```bash
git add backend/.gitignore .github/workflows/llm-evals.yml
git commit -m "🙈 chore: gitignore eval results directory and ensure it exists in CI"
```

---

### Task 14: Exclude eval tests from default pytest run

**Files:**
- Modify: `backend/pyproject.toml:32-34`

The eval tests make real LLM API calls and should not run during normal `uv run pytest`. They should only run when explicitly targeted.

- [ ] **Step 1: Add eval test exclusion to pytest config**

In `backend/pyproject.toml`, update the `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=glean --cov-report=term-missing --cov-fail-under=80 --ignore=tests/evals"
markers = ["soft_gate: marks tests as soft-gate evaluations (deselect with '-m \"not soft_gate\"')"]
```

The `--ignore=tests/evals` flag means `uv run pytest` (the normal CI and dev command) skips the eval directory entirely. To run evals, you explicitly target them: `uv run pytest tests/evals/`.

- [ ] **Step 2: Verify existing tests still run and pass**

Run: `cd backend && uv run pytest -v`
Expected: All existing tests pass, no eval tests appear in output

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "⚙️ chore: exclude eval tests from default pytest run"
```

---

### Task 15: End-to-end smoke test (local)

This task verifies the full setup works locally with a real LLM call (uses your Anthropic key from `.env`).

- [ ] **Step 1: Run a single structural eval test to verify wiring**

Run: `cd backend && GLEAN_LLM_PROVIDER=anthropic GLEAN_LLM_MODEL=claude-sonnet-4-6 uv run pytest tests/evals/test_receipt_scan.py::TestReceiptScanStructural::test_all_examples_return_valid_json -v --no-cov -s`

Expected: 1 passed (makes real API calls to Claude, verifies the full pipeline)

- [ ] **Step 2: Run the comment generator against sample XML**

Run: `cd backend && uv run python -c "
import sys; sys.path.insert(0, 'scripts')
from generate_eval_comment import TestResult, generate_comment
comment = generate_comment(
    [TestResult('test_json', 'tests.evals.test_receipt_scan.TestReceiptScanStructural', True)],
    [TestResult('test_lower', 'tests.evals.test_receipt_scan.TestReceiptScanHeuristic', True)],
    'anthropic/claude-sonnet-4-6'
)
print(comment)
"`

Expected: Renders the jazzy markdown comment to stdout

- [ ] **Step 3: Verify sync script imports correctly**

Run: `cd backend && uv run python -c "import sys; sys.path.insert(0, 'scripts'); from sync_eval_datasets import main; print('OK')"`
Expected: `OK` (doesn't run the sync, just verifies the import)

- [ ] **Step 4: Run pre-commit to verify code quality**

Run: `cd backend && uv run ruff check src/ tests/ scripts/`
Expected: No lint errors

- [ ] **Step 5: Commit any fixes**

If pre-commit or ruff found issues, fix them and commit:

```bash
git add -u
git commit -m "🧹 chore: fix lint issues from eval framework"
```
