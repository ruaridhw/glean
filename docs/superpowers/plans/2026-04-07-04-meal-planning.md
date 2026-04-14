# Meal Planning & Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Plan tab (N configurable meal slots), single-slot AI suggestions, full-week generation via Claude, mark-as-cooked with pantry decrement, and auto-population of the shopping list when a recipe is added to the plan.

**Architecture:** The Plan tab is a flat list of N `meal_plan_entries` rows. Pantry context is compressed by app logic before being sent to Claude — only the top 15 urgency-scored items are included. The suggestion endpoint accepts pantry context + recipe history + user config and returns ranked recipe suggestions. Marking a meal as cooked triggers a local SQLite transaction that decrements pantry quantities and stamps `last_used_at`.

**Tech Stack:** expo-sqlite, FastAPI, anthropic SDK (claude-sonnet-4-6), Pydantic v2, pytest, Jest + React Native Testing Library

**Depends on:** Plan 1 (Foundation), Plan 2 (Pantry), Plan 3 (Recipes) — all DB tables, pantry queries, ingredient resolution, and recipe queries must exist.

---

## File Structure

```
mobile/
  app/(tabs)/plan/
    index.tsx                    # Plan screen: N slot list
  src/
    db/
      plan.ts                    # SQLite queries: meal plan CRUD + mark cooked
      shopping.ts                # Extended: add items from recipe gap
    suggestions/
      compress.ts                # Pantry context compression (app logic)

backend/
  src/glean/
    suggestions/
      router.py                  # POST /suggestions
      service.py                 # Claude orchestration
      schemas.py                 # SuggestionRequest, SuggestionResponse
  tests/
    suggestions/
      test_router.py
      test_compress.py           # Tests for compression logic (mobile, run via Jest)
      fixtures/
        suggestion_claude.json   # Mocked Claude suggestion response
```

---

### Task 1: Plan SQLite queries

**Files:**
- Create: `mobile/src/db/plan.ts`

- [ ] **Step 1: Write plan.ts**

```typescript
// mobile/src/db/plan.ts
import { getDb } from './client';
import { normalizeUnit } from '@/normalization/units';
import type { MealPlanEntry } from '@/types';

export async function getMealPlanEntries(): Promise<MealPlanEntry[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<MealPlanEntry>(
    `SELECT mpe.*, r.title AS recipe_title
     FROM meal_plan_entries mpe
     JOIN recipes r ON mpe.recipe_id = r.id
     ORDER BY mpe.id ASC`
  );
  return rows.map(r => ({ ...r, cooked_at: r.cooked_at ?? null }));
}

export async function getMealPlanCount(): Promise<number> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ count: number }>(
    'SELECT COUNT(*) AS count FROM meal_plan_entries'
  );
  return row?.count ?? 0;
}

export async function addMealPlanEntry(recipeId: number, servings: number = 1): Promise<number> {
  const db = await getDb();
  const result = await db.runAsync(
    `INSERT INTO meal_plan_entries (recipe_id, planned_date, servings)
     VALUES (?, date('now'), ?)`,
    [recipeId, servings]
  );
  return result.lastInsertRowId;
}

export async function deleteMealPlanEntry(id: number): Promise<void> {
  const db = await getDb();
  await db.runAsync('DELETE FROM meal_plan_entries WHERE id = ?', [id]);
}

// Marks a meal as cooked:
// 1. Sets cooked_at on the entry
// 2. Decrements pantry quantities (floor at 0)
// 3. Stamps last_used_at on affected pantry rows
// 4. Stamps last_cooked_at on the recipe
export async function markMealAsCooked(entryId: number): Promise<void> {
  const db = await getDb();

  const entry = await db.getFirstAsync<{ recipe_id: number; servings: number }>(
    'SELECT recipe_id, servings FROM meal_plan_entries WHERE id = ?',
    [entryId]
  );
  if (!entry) throw new Error(`Meal plan entry ${entryId} not found`);

  const ingredients = await db.getAllAsync<{ ingredient_id: number; quantity: number; unit: string }>(
    'SELECT ingredient_id, quantity, unit FROM recipe_ingredients WHERE recipe_id = ?',
    [entry.recipe_id]
  );

  const now = new Date().toISOString();

  for (const ing of ingredients) {
    // Get the canonical_unit for this ingredient
    const ingredientRow = await db.getFirstAsync<{ canonical_unit: string | null; canonical_name: string }>(
      'SELECT canonical_unit, canonical_name FROM ingredients WHERE id = ?',
      [ing.ingredient_id]
    );

    // Get the pantry unit for this ingredient
    const pantryRow = await db.getFirstAsync<{ unit: string }>(
      'SELECT unit FROM pantry_items WHERE ingredient_id = ?',
      [ing.ingredient_id]
    );

    // Normalize the recipe quantity to the pantry's stored unit
    let decrementQuantity = ing.quantity * entry.servings;
    if (pantryRow && ingredientRow) {
      const normalized = normalizeUnit({
        quantity: ing.quantity * entry.servings,
        unit: ing.unit,
        canonicalUnit: pantryRow.unit,  // Normalize to whatever the pantry has stored
        canonicalName: ingredientRow.canonical_name,
      });
      if (normalized) {
        decrementQuantity = normalized.quantity;
      }
    }

    await db.runAsync(
      `UPDATE pantry_items
       SET quantity = MAX(0, quantity - ?),
           last_used_at = ?,
           updated_at = datetime('now')
       WHERE ingredient_id = ?`,
      [decrementQuantity, now, ing.ingredient_id]
    );
  }

  await db.runAsync(
    `UPDATE recipes SET last_cooked_at = ? WHERE id = ?`,
    [now, entry.recipe_id]
  );

  await db.runAsync(
    `UPDATE meal_plan_entries SET cooked_at = ? WHERE id = ?`,
    [now, entryId]
  );
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/plan.test.ts
import { markMealAsCooked, addMealPlanEntry } from '@/db/plan';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('markMealAsCooked', () => {
  it('decrements pantry with normalization, stamps last_used_at, and sets cooked_at', async () => {
    const runCalls: Array<[string, unknown[]]> = [];
    let getFirstCallCount = 0;
    const mockDb = {
      getFirstAsync: jest.fn().mockImplementation(async (sql: string) => {
        getFirstCallCount++;
        if (sql.includes('meal_plan_entries')) return { recipe_id: 2, servings: 1 };
        if (sql.includes('canonical_unit')) return { canonical_unit: 'g', canonical_name: 'chicken breast' };
        if (sql.includes('pantry_items') && sql.includes('unit')) return { unit: 'g' };
        return null;
      }),
      getAllAsync: jest.fn()
        .mockResolvedValueOnce([
          { ingredient_id: 10, quantity: 200, unit: 'g' },
        ]),
      runAsync: jest.fn().mockImplementation((sql: string, params: unknown[]) => {
        runCalls.push([sql, params]);
      }),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await markMealAsCooked(5);

    // Pantry decrement for ingredient 10 (200g × 1 serving, already in g, no conversion)
    expect(runCalls.some(([sql, params]) =>
      sql.includes('UPDATE pantry_items') &&
      (params as unknown[])[0] === 200 &&
      (params as unknown[])[2] === 10
    )).toBe(true);

    // last_cooked_at on recipe
    expect(runCalls.some(([sql]) => sql.includes('UPDATE recipes SET last_cooked_at'))).toBe(true);

    // cooked_at on entry
    expect(runCalls.some(([sql]) => sql.includes('UPDATE meal_plan_entries SET cooked_at'))).toBe(true);
  });

  it('throws when entry not found', async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue(null),
      getAllAsync: jest.fn(),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await expect(markMealAsCooked(999)).rejects.toThrow('not found');
  });
});

describe('addMealPlanEntry', () => {
  it('inserts and returns new id', async () => {
    const mockDb = { runAsync: jest.fn().mockResolvedValue({ lastInsertRowId: 7 }) };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    const id = await addMealPlanEntry(3);
    expect(id).toBe(7);
    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('INSERT INTO meal_plan_entries'),
      expect.arrayContaining([3, 1])
    );
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/plan.test.ts --verbose
```
Expected: 3 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/plan.ts mobile/src/__tests__/db/plan.test.ts
git commit -m "📅 db: meal plan SQLite queries + mark-as-cooked pantry decrement"
```

---

### Task 2: Shopping list auto-population from recipe plan

**Files:**
- Modify: `mobile/src/db/shopping.ts`

- [ ] **Step 1: Add gap computation to shopping.ts**

```typescript
// Append to mobile/src/db/shopping.ts

import { getDb } from './client';

export interface ShoppingListItem {
  id: number;
  ingredient_id: number | null;
  name: string;
  quantity: number | null;
  unit: string | null;
  source: 'manual' | 'meal_plan';
  is_checked: boolean;
}

export async function getShoppingListItems(): Promise<ShoppingListItem[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<ShoppingListItem>(
    `SELECT sli.*, COALESCE(i.canonical_name, sli.name) AS name
     FROM shopping_list_items sli
     LEFT JOIN ingredients i ON sli.ingredient_id = i.id
     ORDER BY sli.is_checked ASC, sli.id DESC`
  );
  return rows.map(r => ({ ...r, is_checked: Boolean(r.is_checked) }));
}

// When a recipe is added to the plan, compute which ingredients are
// insufficient in the pantry and add them to the shopping list.
export async function addShoppingGapsForRecipe(
  recipeId: number,
  servings: number = 1
): Promise<void> {
  const db = await getDb();

  const recipeIngredients = await db.getAllAsync<{
    ingredient_id: number;
    canonical_name: string;
    quantity: number;
    unit: string;
  }>(
    `SELECT ri.ingredient_id, i.canonical_name, ri.quantity, ri.unit
     FROM recipe_ingredients ri
     JOIN ingredients i ON ri.ingredient_id = i.id
     WHERE ri.recipe_id = ? AND ri.is_optional = 0`,
    [recipeId]
  );

  for (const ing of recipeIngredients) {
    const needed = ing.quantity * servings;
    const pantryRow = await db.getFirstAsync<{ quantity: number }>(
      'SELECT quantity FROM pantry_items WHERE ingredient_id = ?',
      [ing.ingredient_id]
    );
    const available = pantryRow?.quantity ?? 0;

    if (available < needed) {
      const shortfall = needed - available;
      // Don't duplicate — check if already on list
      const existing = await db.getFirstAsync<{ id: number }>(
        `SELECT id FROM shopping_list_items
         WHERE ingredient_id = ? AND is_checked = 0`,
        [ing.ingredient_id]
      );
      if (!existing) {
        await db.runAsync(
          `INSERT INTO shopping_list_items (ingredient_id, name, quantity, unit, source)
           VALUES (?, ?, ?, ?, 'meal_plan')`,
          [ing.ingredient_id, ing.canonical_name, shortfall, ing.unit]
        );
      }
    }
  }
}

export async function checkOffByIngredientIds(ingredientIds: number[]): Promise<void> {
  if (ingredientIds.length === 0) return;
  const db = await getDb();
  const placeholders = ingredientIds.map(() => '?').join(', ');
  await db.runAsync(
    `UPDATE shopping_list_items SET is_checked = 1 WHERE ingredient_id IN (${placeholders})`,
    ingredientIds
  );
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/shopping-gaps.test.ts
import { addShoppingGapsForRecipe } from '@/db/shopping';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('addShoppingGapsForRecipe', () => {
  it('adds shortfall item when pantry has less than needed', async () => {
    const insertCalls: unknown[][] = [];
    const mockDb = {
      getAllAsync: jest.fn().mockResolvedValue([
        { ingredient_id: 1, canonical_name: 'chicken breast', quantity: 400, unit: 'g' },
      ]),
      getFirstAsync: jest.fn()
        .mockResolvedValueOnce({ quantity: 200 })  // pantry has 200g
        .mockResolvedValueOnce(null),               // not already on list
      runAsync: jest.fn().mockImplementation((_sql: string, params: unknown[]) => {
        insertCalls.push(params);
      }),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await addShoppingGapsForRecipe(1, 1);

    // Shortfall = 400 - 200 = 200g
    expect(insertCalls[0]).toEqual(expect.arrayContaining([1, 'chicken breast', 200, 'g']));
  });

  it('skips when pantry already has enough', async () => {
    const mockDb = {
      getAllAsync: jest.fn().mockResolvedValue([
        { ingredient_id: 1, canonical_name: 'salt', quantity: 50, unit: 'g' },
      ]),
      getFirstAsync: jest.fn().mockResolvedValue({ quantity: 500 }),  // pantry has 500g
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await addShoppingGapsForRecipe(1, 1);

    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });

  it('skips when item already on shopping list', async () => {
    const mockDb = {
      getAllAsync: jest.fn().mockResolvedValue([
        { ingredient_id: 2, canonical_name: 'pasta', quantity: 200, unit: 'g' },
      ]),
      getFirstAsync: jest.fn()
        .mockResolvedValueOnce({ quantity: 0 })    // pantry empty
        .mockResolvedValueOnce({ id: 3 }),         // already on list
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await addShoppingGapsForRecipe(1, 1);

    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/shopping-gaps.test.ts --verbose
```
Expected: 3 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/shopping.ts mobile/src/__tests__/db/shopping-gaps.test.ts
git commit -m "🛒 db: auto-populate shopping list gaps when recipe added to plan"
```

---

### Task 3: Pantry context compression

**Files:**
- Create: `mobile/src/suggestions/compress.ts`

- [ ] **Step 1: Write compress.ts**

```typescript
// mobile/src/suggestions/compress.ts

export interface PantryItemForCompression {
  ingredient_id: number;
  canonical_name: string;
  quantity: number;
  unit: string;
  expiry_date: string | null;
  last_used_at: string | null;
  is_staple: boolean;
  food_group: string;
}

export interface CompressedPantryItem {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  food_group: string;
  urgency_score: number;
}

const MS_PER_DAY = 1000 * 60 * 60 * 24;

// Scores a pantry item's urgency (higher = more urgent to use).
// Factors: expiry proximity, time since last use, quantity level.
export function scorePantryItem(
  item: PantryItemForCompression,
  now: Date = new Date()
): number {
  let score = 0;

  if (item.expiry_date) {
    const daysUntilExpiry = (new Date(item.expiry_date).getTime() - now.getTime()) / MS_PER_DAY;
    if (daysUntilExpiry <= 1) score += 100;
    else if (daysUntilExpiry <= 3) score += 50;
    else if (daysUntilExpiry <= 7) score += 20;
  }

  if (item.last_used_at) {
    const daysSinceUsed = (now.getTime() - new Date(item.last_used_at).getTime()) / MS_PER_DAY;
    score += Math.min(30, daysSinceUsed);  // Cap at 30 points
  } else {
    score += 15;  // Never used — moderate urgency
  }

  if (item.quantity > 0 && item.quantity < 100) score += 10;

  return score;
}

// Compresses full pantry to top-N items by urgency score.
// Excludes staples (assumed always available).
export function compressPantry(
  items: PantryItemForCompression[],
  topN: number = 15,
  now: Date = new Date()
): CompressedPantryItem[] {
  return items
    .filter(item => !item.is_staple && item.quantity > 0)
    .map(item => ({ ...item, urgency_score: scorePantryItem(item, now) }))
    .sort((a, b) => b.urgency_score - a.urgency_score)
    .slice(0, topN)
    .map(item => ({
      id: item.ingredient_id,
      name: item.canonical_name,
      quantity: item.quantity,
      unit: item.unit,
      food_group: item.food_group,
      urgency_score: item.urgency_score,
    }));
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/suggestions/compress.test.ts
import { scorePantryItem, compressPantry } from '@/suggestions/compress';
import type { PantryItemForCompression } from '@/suggestions/compress';

const baseItem: PantryItemForCompression = {
  ingredient_id: 1,
  canonical_name: 'chicken breast',
  quantity: 400,
  unit: 'g',
  expiry_date: null,
  last_used_at: null,
  is_staple: false,
  food_group: 'protein',
};

const now = new Date('2026-04-07T12:00:00Z');

describe('scorePantryItem', () => {
  it('scores higher when item expires tomorrow', () => {
    const expiringSoon = { ...baseItem, expiry_date: '2026-04-08' };
    const notExpiring = { ...baseItem, expiry_date: '2026-04-20' };
    expect(scorePantryItem(expiringSoon, now)).toBeGreaterThan(scorePantryItem(notExpiring, now));
  });

  it('scores higher when item not used recently', () => {
    const stale = { ...baseItem, last_used_at: '2026-03-07T00:00:00Z' };   // 31 days ago
    const fresh = { ...baseItem, last_used_at: '2026-04-06T00:00:00Z' };   // 1 day ago
    expect(scorePantryItem(stale, now)).toBeGreaterThan(scorePantryItem(fresh, now));
  });
});

describe('compressPantry', () => {
  it('excludes staples', () => {
    const items: PantryItemForCompression[] = [
      { ...baseItem, ingredient_id: 1, is_staple: true },
      { ...baseItem, ingredient_id: 2, canonical_name: 'salmon', is_staple: false },
    ];
    const result = compressPantry(items, 15, now);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('salmon');
  });

  it('excludes zero-quantity items', () => {
    const items: PantryItemForCompression[] = [
      { ...baseItem, ingredient_id: 1, quantity: 0 },
      { ...baseItem, ingredient_id: 2, canonical_name: 'salmon', quantity: 200 },
    ];
    const result = compressPantry(items, 15, now);
    expect(result).toHaveLength(1);
  });

  it('returns at most topN items sorted by urgency', () => {
    const items: PantryItemForCompression[] = Array.from({ length: 20 }, (_, i) => ({
      ...baseItem,
      ingredient_id: i + 1,
      canonical_name: `ingredient-${i}`,
      expiry_date: i < 5 ? '2026-04-08' : null,  // First 5 expire soon
    }));
    const result = compressPantry(items, 10, now);
    expect(result).toHaveLength(10);
    // Expiring items should appear first
    expect(result[0].urgency_score).toBeGreaterThanOrEqual(result[9].urgency_score);
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/suggestions/compress.test.ts --verbose
```
Expected: 5 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/suggestions/compress.ts mobile/src/__tests__/suggestions/compress.test.ts
git commit -m "🗜 suggestions: pantry context compression by urgency score"
```

---

### Task 4: Backend — suggestions endpoint

**Files:**
- Create: `backend/src/glean/suggestions/schemas.py`
- Create: `backend/src/glean/suggestions/service.py`
- Create: `backend/src/glean/suggestions/router.py`
- Create: `backend/tests/suggestions/test_router.py`
- Create: `backend/tests/suggestions/fixtures/suggestion_claude.json`

- [ ] **Step 1: Write suggestions/schemas.py**

```python
# backend/src/glean/suggestions/schemas.py
from pydantic import BaseModel


class CompressedPantryItem(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    food_group: str
    urgency_score: float


class RecipeHistoryItem(BaseModel):
    recipe_id: int
    title: str
    last_cooked_at: str | None  # ISO datetime or null
    food_groups: list[str]


class SuggestionRequest(BaseModel):
    pantry: list[CompressedPantryItem]
    recipe_history: list[RecipeHistoryItem]  # last_cooked_at for all saved recipes
    food_group_coverage: dict[str, int]       # food_group → meals cooked this week
    purchase_tolerance: float                 # 0.0–1.0
    meals_per_week: int
    dietary_flags: list[str]                  # User dietary preferences
    max_active_time_mins: int | None


class SuggestedRecipe(BaseModel):
    recipe_id: int
    title: str
    reason: str                    # Human-readable explanation
    missing_ingredients: list[str] # Non-pantry ingredients needed


class SuggestionResponse(BaseModel):
    suggestions: list[SuggestedRecipe]
```

- [ ] **Step 2: Write test fixture**

```json
// backend/tests/suggestions/fixtures/suggestion_claude.json
[
  {
    "recipe_id": 1,
    "title": "Chicken Stir Fry",
    "reason": "Uses chicken breast expiring in 2 days and you haven't cooked it in 3 weeks.",
    "missing_ingredients": ["soy sauce"]
  },
  {
    "recipe_id": 3,
    "title": "Lentil Soup",
    "reason": "No protein dish this week and lentils have been unused for 12 days.",
    "missing_ingredients": []
  }
]
```

- [ ] **Step 3: Write suggestions/service.py**

```python
# backend/src/glean/suggestions/service.py
import json
import anthropic
from glean.config import get_settings
from glean.observability import logger, tracer
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse, SuggestedRecipe

SUGGESTION_SYSTEM_PROMPT = """You are a meal planning assistant for the Glean app.
Given a user's pantry, recipe history, and preferences, suggest meals to cook this week.

Rules:
- Prioritise recipes that use pantry items with high urgency scores (expiring soon, unused long)
- Balance food group coverage across the week
- Respect dietary flags (never suggest recipes incompatible with user's dietary_flags)
- Respect purchase_tolerance (0.0 = only pantry ingredients; 1.0 = any recipe)
- Prefer recipes not cooked recently (further last_cooked_at = higher priority)
- Return up to meals_per_week suggestions

Respond with a JSON array of objects:
[{"recipe_id": <int>, "title": <str>, "reason": <str explaining why>, "missing_ingredients": [<ingredient names not in pantry>]}]

Respond with ONLY valid JSON. No markdown."""


@tracer.capture_method
def get_suggestions(request: SuggestionRequest) -> SuggestionResponse:
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    context = {
        "pantry": [item.model_dump() for item in request.pantry],
        "recipe_history": [r.model_dump() for r in request.recipe_history],
        "food_group_coverage_this_week": request.food_group_coverage,
        "purchase_tolerance": request.purchase_tolerance,
        "meals_per_week": request.meals_per_week,
        "dietary_flags": request.dietary_flags,
        "max_active_time_mins": request.max_active_time_mins,
    }

    logger.info("requesting suggestions", extra={
        "pantry_items": len(request.pantry),
        "recipes": len(request.recipe_history),
    })

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SUGGESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(context)}],
    )
    raw = json.loads(message.content[0].text)
    logger.info("suggestions received", extra={"count": len(raw), "tokens": message.usage.input_tokens})

    suggestions = [SuggestedRecipe(**item) for item in raw]
    return SuggestionResponse(suggestions=suggestions)
```

> **Note on `dietary_flags`:** The `dietary_flags` field on `SuggestionRequest` carries user dietary preferences sent from the mobile app. Recipe-level dietary flags now come from the `recipe_dietary_flags` join table (not a JSON column) as established in Plan 3. The `Recipe` TypeScript type's `dietary_flags: string[]` field is populated correctly by the updated `getRecipeById`/`getSavedRecipes` from Plan 3, so no change is needed to `compress.ts` or the plan screen's recipe mapping — the data flows through correctly as-is.

- [ ] **Step 4: Write suggestions/router.py**

```python
# backend/src/glean/suggestions/router.py
from fastapi import APIRouter, Depends
from glean.dependencies import verify_cognito_token
from glean.suggestions import service
from glean.suggestions.schemas import SuggestionRequest, SuggestionResponse

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("", response_model=SuggestionResponse, dependencies=[Depends(verify_cognito_token)])
def get_suggestions(request: SuggestionRequest) -> SuggestionResponse:
    return service.get_suggestions(request)
```

- [ ] **Step 5: Register router in main.py**

```python
# backend/src/glean/main.py — add after recipes_router import
from glean.suggestions.router import router as suggestions_router
app.include_router(suggestions_router)
```

- [ ] **Step 6: Write tests**

```python
# backend/tests/suggestions/test_router.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_REQUEST = {
    "pantry": [
        {"id": 1, "name": "chicken breast", "quantity": 400, "unit": "g", "food_group": "protein", "urgency_score": 85.0},
    ],
    "recipe_history": [
        {"recipe_id": 1, "title": "Chicken Stir Fry", "last_cooked_at": "2026-03-17T00:00:00Z", "food_groups": ["protein", "veg"]},
        {"recipe_id": 3, "title": "Lentil Soup", "last_cooked_at": None, "food_groups": ["protein", "carb"]},
    ],
    "food_group_coverage": {"protein": 1, "carb": 2, "veg": 1},
    "purchase_tolerance": 0.3,
    "meals_per_week": 5,
    "dietary_flags": [],
    "max_active_time_mins": None,
}


def test_get_suggestions_returns_ranked_list(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fixture = json.loads((FIXTURES / "suggestion_claude.json").read_text())
    mock_content = MagicMock()
    mock_content.text = json.dumps(fixture)
    mock_msg = MagicMock()
    mock_msg.content = [mock_content]
    mock_msg.usage.input_tokens = 400

    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_msg
        response = client.post("/suggestions", headers=auth_headers, json=SAMPLE_REQUEST)

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["title"] == "Chicken Stir Fry"
    assert "expiring" in suggestions[0]["reason"]
    assert suggestions[1]["missing_ingredients"] == []


def test_get_suggestions_requires_auth(client: TestClient) -> None:
    response = client.post("/suggestions", json=SAMPLE_REQUEST)
    assert response.status_code == 401
```

- [ ] **Step 7: Run tests**

```bash
cd backend && uv run pytest tests/suggestions/ -v
```
Expected: 2 passing

- [ ] **Step 8: Commit**

```bash
git add backend/src/glean/suggestions/ backend/tests/suggestions/
git commit -m "🤖 suggestions: Claude meal suggestion endpoint"
```

---

### Task 5: Plan screen (mobile)

**Files:**
- Modify: `mobile/app/(tabs)/plan/index.tsx`

- [ ] **Step 1: Write plan/index.tsx**

```typescript
// mobile/app/(tabs)/plan/index.tsx
import { useState, useCallback } from 'react';
import {
  View, Text, FlatList, Pressable, Alert,
  StyleSheet, ActivityIndicator
} from 'react-native';
import { useFocusEffect, router, useLocalSearchParams } from 'expo-router';
import { getMealPlanEntries, getMealPlanCount, deleteMealPlanEntry, addMealPlanEntry, markMealAsCooked } from '@/db/plan';
import { addShoppingGapsForRecipe } from '@/db/shopping';
import { getUserConfig } from '@/db/config';
import { getPantryItems } from '@/db/pantry';
import { getSavedRecipes } from '@/db/recipes';
import { compressPantry } from '@/suggestions/compress';
import { apiClient } from '@/api/client';
import type { MealPlanEntry } from '@/types';

export default function PlanScreen() {
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const params = useLocalSearchParams<{ add_recipe_id?: string }>();

  const load = useCallback(async () => {
    setLoading(true);
    const [fetchedEntries, config] = await Promise.all([
      getMealPlanEntries(),
      getUserConfig(),
    ]);
    setEntries(fetchedEntries);
    setMealsPerWeek(config.meals_per_week);
    setLoading(false);
  }, []);

  useFocusEffect(useCallback(() => {
    load();
    // Handle "Add to Plan" nav from recipe detail
    if (params.add_recipe_id) {
      handleAddRecipe(Number(params.add_recipe_id));
    }
  }, [load, params.add_recipe_id]));

  async function handleAddRecipe(recipeId: number) {
    const count = await getMealPlanCount();
    if (count >= mealsPerWeek) {
      Alert.alert('Plan full', `You already have ${mealsPerWeek} meals planned.`);
      return;
    }
    await addMealPlanEntry(recipeId);
    await addShoppingGapsForRecipe(recipeId);
    await load();
  }

  async function handleMarkCooked(entry: MealPlanEntry) {
    Alert.alert(
      'Mark as cooked?',
      `This will decrement pantry quantities for "${entry.recipe_title}".`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Mark Cooked', onPress: async () => {
          await markMealAsCooked(entry.id);
          await load();
        }},
      ]
    );
  }

  async function handleDelete(entry: MealPlanEntry) {
    await deleteMealPlanEntry(entry.id);
    await load();
  }

  async function generateWeek() {
    const emptySlots = mealsPerWeek - entries.length;
    if (emptySlots <= 0) {
      Alert.alert('Plan is full', 'Remove some meals before generating.');
      return;
    }
    setGenerating(true);
    try {
      const [pantryItems, recipes, config] = await Promise.all([
        getPantryItems(),
        getSavedRecipes(),
        getUserConfig(),
      ]);

      const compressed = compressPantry(pantryItems as any);
      const recipeHistory = recipes.map(r => ({
        recipe_id: r.id,
        title: r.title,
        last_cooked_at: r.last_cooked_at,
        food_groups: [],
      }));

      const result = await apiClient.post<{ suggestions: Array<{ recipe_id: number }> }>('/suggestions', {
        pantry: compressed,
        recipe_history: recipeHistory,
        food_group_coverage: {},
        purchase_tolerance: config.purchase_tolerance,
        meals_per_week: emptySlots,
        dietary_flags: config.dietary_flags,
        max_active_time_mins: config.max_active_time_mins,
      });

      for (const suggestion of result.suggestions.slice(0, emptySlots)) {
        await addMealPlanEntry(suggestion.recipe_id);
        await addShoppingGapsForRecipe(suggestion.recipe_id);
      }
      await load();
    } catch {
      Alert.alert('Generation failed', 'Could not generate suggestions. Try again.');
    } finally {
      setGenerating(false);
    }
  }

  const emptySlots = Math.max(0, mealsPerWeek - entries.length);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.heading}>This Week</Text>
        <Pressable
          style={[styles.generateBtn, generating && styles.generateBtnDisabled]}
          onPress={generateWeek}
          disabled={generating}
        >
          {generating
            ? <ActivityIndicator size="small" color="#fff" />
            : <Text style={styles.generateBtnText}>Generate week</Text>
          }
        </Pressable>
      </View>

      <FlatList
        data={[
          ...entries,
          ...Array.from({ length: emptySlots }, (_, i) => ({ id: -(i + 1), isEmpty: true })),
        ]}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => {
          if ('isEmpty' in item) {
            return (
              <Pressable
                style={styles.emptySlot}
                onPress={() => router.push('/(tabs)/meals/search')}
              >
                <Text style={styles.emptySlotText}>+ Add a meal</Text>
              </Pressable>
            );
          }
          const entry = item as MealPlanEntry;
          return (
            <View style={[styles.entryRow, entry.cooked_at && styles.cookedRow]}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.entryTitle, entry.cooked_at && styles.cookedTitle]}>
                  {entry.recipe_title}
                </Text>
                {entry.cooked_at && <Text style={styles.cookedLabel}>Cooked ✓</Text>}
              </View>
              {!entry.cooked_at && (
                <Pressable style={styles.cookBtn} onPress={() => handleMarkCooked(entry)}>
                  <Text style={styles.cookBtnText}>Cooked</Text>
                </Pressable>
              )}
              <Pressable onPress={() => handleDelete(entry)} style={styles.deleteBtn}>
                <Text style={styles.deleteBtnText}>✕</Text>
              </Pressable>
            </View>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16 },
  heading: { fontSize: 24, fontWeight: '700' },
  generateBtn: { backgroundColor: '#2a9d8f', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  generateBtnDisabled: { opacity: 0.5 },
  generateBtnText: { color: '#fff', fontWeight: '600', fontSize: 13 },
  entryRow: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee' },
  cookedRow: { opacity: 0.6 },
  entryTitle: { fontSize: 15, fontWeight: '600' },
  cookedTitle: { textDecorationLine: 'line-through' },
  cookedLabel: { fontSize: 11, color: '#2a9d8f', marginTop: 2 },
  cookBtn: { borderWidth: 1, borderColor: '#2a9d8f', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4, marginRight: 8 },
  cookBtnText: { color: '#2a9d8f', fontSize: 12 },
  deleteBtn: { padding: 4 },
  deleteBtnText: { color: '#ccc', fontSize: 16 },
  emptySlot: { padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee', borderStyle: 'dashed' },
  emptySlotText: { color: '#aaa', fontSize: 14 },
});
```

- [ ] **Step 2: Add getUserConfig to db/config.ts**

```typescript
// mobile/src/db/config.ts
import { getDb } from './client';
import type { UserConfig } from '@/types';

export async function getUserConfig(): Promise<UserConfig> {
  const db = await getDb();
  const row = await db.getFirstAsync<UserConfig & { dietary_flags: string }>(
    'SELECT * FROM user_config WHERE id = 1'
  );
  if (!row) return { purchase_tolerance: 0.5, preferred_servings: 2, meals_per_week: 5, dietary_flags: [], max_active_time_mins: null };
  return { ...row, dietary_flags: JSON.parse(row.dietary_flags) };
}

export async function updateUserConfig(patch: Partial<Omit<UserConfig, 'dietary_flags'> & { dietary_flags: string[] }>): Promise<void> {
  const db = await getDb();
  const current = await getUserConfig();
  const updated = { ...current, ...patch };
  await db.runAsync(
    `UPDATE user_config SET purchase_tolerance = ?, preferred_servings = ?, meals_per_week = ?, dietary_flags = ?, max_active_time_mins = ? WHERE id = 1`,
    [updated.purchase_tolerance, updated.preferred_servings, updated.meals_per_week, JSON.stringify(updated.dietary_flags), updated.max_active_time_mins ?? null]
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add mobile/app/(tabs)/plan/ mobile/src/db/config.ts
git commit -m "📅 plan: meal plan screen with generate week and mark as cooked"
```
