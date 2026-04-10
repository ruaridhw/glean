# LLM Evaluation Framework — Design Spec

**Date:** 2026-04-09
**Approach:** Hybrid — Pytest assertions + LangSmith datasets & monitoring (Approach C)

## Overview

A three-layer evaluation framework for Glean's Claude integrations (receipt scanning, meal suggestions, recipe import) covering:

1. **Offline evals** — pytest-based test suites run manually in CI against golden datasets
2. **Online monitoring** — LangSmith tracing on all production Claude calls with dashboards and alerting
3. **Dataset evolution** — production traces reviewed via LangSmith annotation queue, promoted to golden datasets via PR

## Goals

- **Prompt regression detection** — catch quality degradation when prompts change
- **Model migration safety** — validate prompts against cheaper/different models before switching
- **Ongoing quality monitoring** — track production output quality and catch degradation early

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CI (GitHub Actions)                  │
│                                                         │
│  workflow_dispatch (manual trigger)                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │  pytest tests/evals/                              │  │
│  │  ├─ Layer 1: Structural (hard gate)               │  │
│  │  ├─ Layer 2: Heuristic (soft gate)                │  │
│  │  └─ Layer 3: LLM-as-judge (soft gate)             │  │
│  └───────────────────┬───────────────────────────────┘  │
│                      │                                   │
│              gh pr comment (jazzy report)                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                 Production (Lambda)                      │
│                                                         │
│  LangChain ChatModel.invoke()                           │
│       │                                                 │
│       ├─ LangSmith tracing (always-on)                  │
│       └─ Tagged: feature, environment                   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    LangSmith                            │
│                                                         │
│  glean-prod project:                                    │
│  ├─ Dashboards (latency, tokens, cost, error rate)      │
│  ├─ Alerts (error spike, latency spike, cost anomaly)   │
│  └─ Annotation queue (flagged traces → human review)    │
│                                                         │
│  glean-evals project:                                   │
│  └─ CI eval traces (separate from production)           │
│                                                         │
│  Datasets (read-only mirror of git fixtures):           │
│  ├─ receipt-scan                                        │
│  ├─ suggestions                                         │
│  └─ recipe-import                                       │
└─────────────────────────────────────────────────────────┘
```

## Section 1: LangSmith Tracing Integration

### Configuration

LangChain's built-in LangSmith callbacks are activated via environment variables — no code changes to `.invoke()` call sites.

**Environment variables:**

| Variable | Local dev | CI evals | Production |
|---|---|---|---|
| `LANGCHAIN_TRACING_V2` | `false` (opt-in) | `true` | `true` |
| `LANGCHAIN_API_KEY` | optional in `.env` | GitHub Actions secret | AWS Secrets Manager |
| `LANGCHAIN_PROJECT` | `glean-dev` | `glean-evals` | `glean-prod` |

### Trace metadata

All traces are tagged with:
- `feature`: `receipt-scan`, `suggestions`, or `recipe-import`
- `environment`: `dev`, `ci-eval`, or `prod`
- `model_provider`: `anthropic`, `google`, etc.
- `model_name`: the specific model used

This is set via LangChain's `config={"metadata": {...}}` parameter on each `.invoke()` call.

### Model abstraction

Services currently hardcode `ChatAnthropic(model=...)`. Refactor to a model-agnostic factory:

```python
# glean/llm.py
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel

def create_chat_model(provider: str, model: str) -> BaseChatModel:
    match provider:
        case "anthropic":
            return ChatAnthropic(model=model)
        case "google":
            return ChatGoogleGenerativeAI(model=model)
        case _:
            raise ValueError(f"Unknown LLM provider: {provider}")
```

**Configuration via `Settings`:**

| Setting | Production | CI Evals |
|---|---|---|
| `GLEAN_LLM_PROVIDER` | `anthropic` | `google` |
| `GLEAN_LLM_MODEL` | `claude-sonnet-4-6` | `gemma-3` |

Services call `create_chat_model(settings.llm_provider, settings.llm_model)` instead of constructing `ChatAnthropic` directly.

## Section 2: Golden Datasets

### Storage

- **Source of truth:** JSON fixture files in `tests/evals/fixtures/` (git-tracked, code-reviewed)
- **LangSmith mirror:** Read-only copy for browsing/annotation UI
- **Sync direction:** One-way push from git → LangSmith via `scripts/sync_eval_datasets.py`

### Datasets

| Dataset | Input shape | Expected output shape | Initial size |
|---|---|---|---|
| `receipt-scan` | Textract line items `{name, quantity, price}[]` | `ParsedIngredient[]` `{name, quantity, unit, unit_price, confidence}` | ~15-20 examples |
| `suggestions` | `{pantry, recipe_history, food_group_coverage, purchase_tolerance, meals_per_week, dietary_flags, max_active_time_mins}` | `SuggestedRecipe[]` `{recipe_id, title, reason, missing_ingredients}` | ~10-15 examples |
| `recipe-import` | Raw HTML string (capped at 8k chars) | `RecipeOut` JSON `{title, ingredients, instructions, ...}` | ~10-15 examples |

### Example fixture (receipt-scan)

```json
{
  "input": {
    "line_items": [
      {"name": "BNLS CHKN BRST 1.2KG", "quantity": 1, "price": 12.99},
      {"name": "WHL MILK 2L", "quantity": 2, "price": 3.50}
    ]
  },
  "expected": {
    "items": [
      {"name": "chicken breast", "quantity": 1200, "unit": "g", "unit_price": 0.01083, "confidence": 0.9},
      {"name": "whole milk", "quantity": 2000, "unit": "ml", "unit_price": 0.00175, "confidence": 0.95}
    ]
  }
}
```

### Expected output handling

- **Structured fields** (name, unit): exact match
- **Numeric fields** (quantity, unit_price): `pytest.approx()` with tolerance
- **Subjective fields** (confidence, reason): reference values scored by LLM-as-judge, not exact-matched

### Seeding

Initial datasets are seeded by running current prompts against representative inputs (using production model), then hand-verifying and correcting outputs.

### Dataset evolution

Production examples flagged via LangSmith's annotation queue are promoted into the fixture files via PR — manual process, not auto-synced.

## Section 3: Evaluator Design

Three layers, cheapest to most expensive:

### Layer 1 — Structural (hard gate)

Pure Python assertions. No LLM calls. Any failure blocks merge.

| Check | receipt-scan | suggestions | recipe-import |
|---|---|---|---|
| Valid JSON | yes | yes | yes |
| Pydantic schema validation | `ParsedIngredient` | `SuggestedRecipe` | `RecipeOut` |
| Required fields present | name, quantity, unit, unit_price, confidence | recipe_id, title, reason, missing_ingredients | title, ingredients, instructions |
| Type correctness | quantity is numeric, unit is string | recipe_id is int, missing_ingredients is list | ingredients is list, instructions is list |
| Enum constraints | unit in `{g, ml, units}` | — | difficulty in allowed set if present |
| Array length | output is non-empty | len <= meals_per_week | ingredients non-empty, instructions >= 2 |

### Layer 2 — Heuristic (soft gate)

Pure Python. Deterministic. Scores reported as percentages.

**receipt-scan:**
- Normalized name is lowercase
- No common abbreviations remaining (BNLS, CHKN, WHL, etc.)
- Quantity > 0
- unit_price > 0
- Confidence between 0.0 and 1.0

**suggestions:**
- `missing_ingredients` items are NOT present in the provided pantry
- `recipe_id` references a recipe from the input history
- Reason string is non-empty and > 10 characters
- Number of suggestions respects `meals_per_week` limit
- No suggestion violates the input `dietary_flags`

**recipe-import:**
- `ingredients` list is non-empty
- `instructions` has at least 2 steps
- `total_time` is valid ISO 8601 duration (if present)
- `source_url` matches the input URL
- No instruction step is empty

### Layer 3 — LLM-as-judge (soft gate)

Uses the cheap eval model (Gemma 3). Scores on a 1-5 rubric.

**receipt-scan judge prompt:**
> Given the raw receipt line item "{raw_name}", the system normalized it to "{normalized_name}" with quantity {quantity}{unit} at {unit_price}/{unit}. Rate the normalization quality 1-5:
> 5 = Perfect canonical name, correct unit conversion, accurate price
> 4 = Minor issue (slightly verbose name, rounding difference)
> 3 = Acceptable but imprecise (name has extra words, unit roughly correct)
> 2 = Significant error (wrong unit type, major quantity error)
> 1 = Wrong (completely misidentified item)
> Respond with only the numeric score.

**suggestions judge prompt:**
> Given this pantry state: {pantry_summary}
> And dietary flags: {dietary_flags}
> The system suggested "{title}" with reason: "{reason}"
> Rate the suggestion quality 1-5:
> 5 = Excellent — uses expiring pantry items, reason is specific and helpful
> 4 = Good — reasonable suggestion, reason references pantry
> 3 = Acceptable — valid recipe but reason is generic
> 2 = Poor — ignores pantry priorities or vague reason
> 1 = Bad — violates dietary flags or completely irrelevant
> Respond with only the numeric score.

**recipe-import judge prompt:**
> Given the source HTML (first 2000 chars): {html_snippet}
> The system extracted this recipe: {extracted_json}
> Rate the extraction quality 1-5:
> 5 = Perfect — all fields accurately captured
> 4 = Minor omission (missing optional field like cuisine or difficulty)
> 3 = Mostly correct but missing some ingredients or steps
> 2 = Significant errors (wrong title, missing most ingredients)
> 1 = Completely wrong extraction
> Respond with only the numeric score.

### Calibration

LLM-as-judge scores are periodically validated against human annotations from LangSmith's annotation queue. If the judge consistently disagrees with human labels, update the rubric prompts.

## Section 4: CI Integration

### GitHub Actions workflow

**Trigger:** `workflow_dispatch` (manual from PR page)

**Steps:**
1. Checkout PR branch
2. Install backend dependencies (`uv sync`)
3. Set environment variables:
   - `GLEAN_LLM_PROVIDER=google`
   - `GLEAN_LLM_MODEL=gemma-3`
   - `LANGCHAIN_TRACING_V2=true`
   - `LANGCHAIN_PROJECT=glean-evals`
4. Run hard gate: `uv run pytest tests/evals/ -m "not soft_gate" -v --tb=short`
5. Run soft gate: `uv run pytest tests/evals/ -m "soft_gate" -v --tb=short --no-header -q` (always exits 0, captures scores)
6. Generate PR comment from results
7. Post via `gh pr comment`

**Secrets:** `LANGCHAIN_API_KEY`, `GOOGLE_API_KEY` stored as GitHub Actions secrets.

### Test structure

```
tests/evals/
├── conftest.py                # Fixtures: load datasets, init model via factory
├── test_receipt_scan.py       # Receipt eval suite
├── test_suggestions.py        # Suggestions eval suite
├── test_recipe_import.py      # Recipe import eval suite
├── judges/
│   ├── __init__.py
│   └── rubrics.py             # LLM-as-judge prompts and scoring logic
└── fixtures/
    ├── receipt_scan.json
    ├── suggestions.json
    └── recipe_import.json
```

### Tiered gating

- **Hard gate:** Tests without the `soft_gate` marker. Standard pytest assertions — any failure = non-zero exit code = red check.
- **Soft gate:** Tests marked `@pytest.mark.soft_gate`. Failures are collected, scores aggregated. Always exits 0. Results reported in PR comment.

### PR comment format

Summary table at the top, collapsible detail sections per feature:

```markdown
## Eval Results — `gemma-3`

| Feature        | Structural | Heuristic | LLM Judge |
|----------------|:----------:|:---------:|:---------:|
| receipt-scan   | 20/20      | 94%       | 4.2/5     |
| suggestions    | 15/15      | 87%       | 3.8/5     |
| recipe-import  | 12/12      | 91%       | 4.0/5     |

**Hard gate:** Passed — all structural checks passed
**Soft gate:** Advisory — suggestions heuristic below 90% threshold

---

<details>
<summary><strong>receipt-scan</strong> — 20/20 structural, 94% heuristic, 4.2/5 judge</summary>

### Structural (hard gate)
All 20 examples produced valid JSON conforming to `ParsedIngredient` schema.

### Heuristic (soft gate)
| Check                        | Pass | Fail | Score |
|------------------------------|------|------|-------|
| Name is lowercase            | 19   | 1    | 95%   |
| No abbreviations remaining   | 18   | 2    | 90%   |
| Quantity > 0                 | 20   | 0    | 100%  |
| Unit in allowed set          | 20   | 0    | 100%  |

**Failed examples:**
- `BNLS CHKN BRST` → `"chkn breast"` (abbreviation not fully expanded)

### LLM Judge (soft gate)
| Score | Count | Examples |
|-------|-------|----------|
| 5     | 14    |          |
| 4     | 4     |          |
| 3     | 2     | `ORG VEG MIX 500G` → scored low on normalization clarity |

</details>

<details>
<summary><strong>suggestions</strong> — 15/15 structural, 87% heuristic, 3.8/5 judge</summary>

...per-check breakdown, failed examples, judge score distribution...

</details>

<details>
<summary><strong>recipe-import</strong> — 12/12 structural, 91% heuristic, 4.0/5 judge</summary>

...per-check breakdown, failed examples, judge score distribution...

</details>

---

View traces in LangSmith: glean-evals project
```

## Section 5: Online Production Monitoring

### LangSmith dashboards (`glean-prod` project)

**Per-feature panels:**
- Latency: p50, p95, p99
- Token usage: input/output tokens per call
- Error rate: JSON parse failures, Pydantic validation failures
- Traces per day
- Cost per day (auto-calculated from token usage)

**Receipt-scan specific:**
- Confidence score distribution histogram — a downward shift signals prompt/model degradation

### Alerting

LangSmith webhook-based alerts routed to notification channel of choice:

| Alert | Condition | Window |
|---|---|---|
| Error rate spike | JSON parse failures > 5% | 1 hour |
| Latency spike | p95 > 10s | 1 hour |
| Cost anomaly | Daily spend > 2x rolling 7-day average | 1 day |

### Annotation queue

- One queue per feature in the `glean-prod` project
- Auto-queue rules:
  - Receipt scans where any item has confidence < 0.7
  - Suggestions where model returned fewer results than `meals_per_week`
  - Recipe imports that fell back to Claude (schema.org extraction failed)
- Human reviewers label traces as good/bad, add corrections
- Promoted examples are added to git fixture files via PR

### Future: implicit feedback loop

Not in scope now, but trace IDs are available to correlate against mobile app signals (user edits a scanned receipt, accepts/rejects a suggestion). The tracing infrastructure supports adding this later without architectural changes.

## Dependencies

### New Python packages

| Package | Purpose | Dependency group |
|---|---|---|
| `langsmith` | SDK for dataset sync, trace querying | production |
| `langchain-google-genai` | Gemma 3 model provider for eval runs | dev/test only |

### External services

| Service | Plan | Estimated cost |
|---|---|---|
| LangSmith | Developer (free) to start | $0 — 5,000 traces/month included. Upgrade to Plus ($39/seat/month) when production traffic exceeds 5k calls/month |
| Google AI (Gemma 3) | Pay-as-you-go | Minimal — only used during CI eval runs |

### GitHub Actions secrets

| Secret | Purpose |
|---|---|
| `LANGCHAIN_API_KEY` | LangSmith access |
| `GOOGLE_API_KEY` | Gemma 3 for LLM-as-judge in CI |

## Out of scope

- Streaming evaluation (all calls are blocking `.invoke()`)
- A/B testing between models in production
- Automated prompt optimization (prompt tuning/DSPy)
- Mobile app feedback integration (future work, infrastructure supports it)
