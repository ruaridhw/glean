# Pantry Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full pantry management — ingredient list UI, receipt scanning via Textract + Claude normalisation, natural language purchase description, manual entry, and the shared review/confirm screen that writes to SQLite and cross-checks the shopping list.

**Architecture:** All persistence is local SQLite. Two AI endpoints on the FastAPI backend handle OCR and NL parsing. Both share a common response schema (`ParsedIngredient[]`) so the mobile app uses a single review screen for both flows. On confirm, pantry is upserted and shopping list items matching by `ingredient_id` are marked checked.

**Tech Stack:** expo-sqlite, expo-camera, Amazon Textract AnalyzeExpense, Claude claude-sonnet-4-6, FastAPI, boto3, anthropic SDK, Pydantic v2, pytest, Jest + React Native Testing Library. Auth uses Cognito JWT (`verify_cognito_token`). On-device unit normalization service (lookup table + density) runs before pantry upsert.

**Depends on:** Plan 1 (Foundation) — SQLite client, types, API client, and navigation shell must exist.

---

## File Structure

```
mobile/
  app/(tabs)/pantry/
    index.tsx                  # Ingredient list screen
    add.tsx                    # FAB action sheet → route to sub-screens
    manual-entry.tsx           # Manual ingredient form
    describe.tsx               # NL description input screen
    scan.tsx                   # Camera screen for receipt
    review.tsx                 # Shared review/confirm screen (receipt + NL)
  src/db/
    pantry.ts                  # SQLite queries: pantry CRUD + upsert
  src/normalization/
    units.ts                   # On-device unit normalization (lookup table + density)

backend/
  src/glean/
    receipts/
      router.py                # POST /receipts/scan, POST /receipts/describe
      service.py               # Textract + Claude orchestration
      schemas.py               # ParsedIngredient, ScanResponse, DescribeRequest
    ingredients/
      router.py                # GET /ingredients/resolve (name → ingredient row)
      service.py               # Ingredient name normalisation via Claude
      schemas.py               # ResolveRequest, ResolvedIngredient
  tests/
    receipts/
      test_router.py
      fixtures/
        receipt_textract.json  # Mocked Textract AnalyzeExpense response
        receipt_claude.json    # Mocked Claude normalisation response
```

---

### Task 1: Pantry SQLite queries

**Files:**
- Create: `mobile/src/db/pantry.ts`

- [ ] **Step 1: Write pantry.ts**

```typescript
// mobile/src/db/pantry.ts
import { getDb } from './client';
import type { PantryItem } from '@/types';

// Returns all pantry items joined with ingredient name + food_group
export async function getPantryItems(): Promise<PantryItem[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<PantryItem>(`
    SELECT
      p.*,
      i.canonical_name,
      i.is_staple,
      ic.food_group
    FROM pantry_items p
    JOIN ingredients i ON p.ingredient_id = i.id
    LEFT JOIN ingredient_categories ic ON i.category = ic.category
    ORDER BY
      CASE WHEN p.expiry_date IS NOT NULL THEN p.expiry_date ELSE '9999-12-31' END ASC,
      CASE WHEN p.last_used_at IS NOT NULL THEN p.last_used_at ELSE '0000-01-01' END ASC
  `);
  return rows;
}

// Upsert: if ingredient already in pantry, add quantity; otherwise insert.
export async function upsertPantryItem(params: {
  ingredient_id: number;
  quantity: number;
  unit: string;
  unit_price?: number | null;
  expiry_date?: string | null;
}): Promise<void> {
  const db = await getDb();
  const existing = await db.getFirstAsync<{ id: number; quantity: number }>(
    'SELECT id, quantity FROM pantry_items WHERE ingredient_id = ?',
    [params.ingredient_id]
  );

  if (existing) {
    await db.runAsync(
      `UPDATE pantry_items
       SET quantity = quantity + ?, unit_price = COALESCE(?, unit_price), updated_at = datetime('now')
       WHERE id = ?`,
      [params.quantity, params.unit_price ?? null, existing.id]
    );
  } else {
    await db.runAsync(
      `INSERT INTO pantry_items (ingredient_id, quantity, unit, unit_price, expiry_date)
       VALUES (?, ?, ?, ?, ?)`,
      [params.ingredient_id, params.quantity, params.unit, params.unit_price ?? null, params.expiry_date ?? null]
    );
  }
}

export async function updatePantryQuantity(id: number, quantity: number): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    `UPDATE pantry_items SET quantity = ?, updated_at = datetime('now') WHERE id = ?`,
    [quantity, id]
  );
}

export async function deletePantryItem(id: number): Promise<void> {
  const db = await getDb();
  await db.runAsync('DELETE FROM pantry_items WHERE id = ?', [id]);
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/pantry.test.ts
import { upsertPantryItem, updatePantryQuantity } from '@/db/pantry';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('upsertPantryItem', () => {
  it('inserts a new row when ingredient not in pantry', async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue(null),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await upsertPantryItem({ ingredient_id: 1, quantity: 500, unit: 'g' });

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('INSERT INTO pantry_items'),
      expect.arrayContaining([1, 500, 'g'])
    );
  });

  it('adds to existing quantity when ingredient already in pantry', async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue({ id: 7, quantity: 200 }),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await upsertPantryItem({ ingredient_id: 1, quantity: 300, unit: 'g' });

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('UPDATE pantry_items'),
      expect.arrayContaining([300, null, 7])
    );
  });
});

describe('updatePantryQuantity', () => {
  it('updates quantity for given id', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await updatePantryQuantity(3, 150);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('UPDATE pantry_items SET quantity = ?'),
      [150, 3]
    );
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/pantry.test.ts --verbose
```
Expected: 3 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/pantry.ts mobile/src/__tests__/db/pantry.test.ts
git commit -m "🥫 db: pantry SQLite queries (upsert, update, delete)"
```

---

### Task 2: Pantry list screen

**Files:**
- Modify: `mobile/app/(tabs)/pantry/index.tsx`

- [ ] **Step 1: Write pantry list screen**

```typescript
// mobile/app/(tabs)/pantry/index.tsx
import { useEffect, useState, useCallback } from 'react';
import {
  View, Text, FlatList, Pressable, TextInput,
  StyleSheet, ActivityIndicator, Alert
} from 'react-native';
import { useFocusEffect, router } from 'expo-router';
import { getPantryItems, updatePantryQuantity, deletePantryItem } from '@/db/pantry';
import type { PantryItem } from '@/types';

export default function PantryScreen() {
  const [items, setItems] = useState<PantryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editQty, setEditQty] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setItems(await getPantryItems());
    setLoading(false);
  }, []);

  useFocusEffect(load);

  async function commitEdit(item: PantryItem) {
    const qty = parseFloat(editQty);
    if (!isNaN(qty) && qty > 0) {
      await updatePantryQuantity(item.id, qty);
    }
    setEditingId(null);
    await load();
  }

  function confirmDelete(item: PantryItem) {
    Alert.alert('Remove from pantry', `Remove ${item.canonical_name}?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: async () => {
        await deletePantryItem(item.id);
        await load();
      }},
    ]);
  }

  const grouped = items.reduce<Record<string, PantryItem[]>>((acc, item) => {
    const group = item.food_group ?? 'other';
    (acc[group] ??= []).push(item);
    return acc;
  }, {});

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Pantry</Text>
      <FlatList
        data={Object.entries(grouped)}
        keyExtractor={([group]) => group}
        renderItem={({ item: [group, groupItems] }) => (
          <View>
            <Text style={styles.groupHeader}>{group.toUpperCase()}</Text>
            {groupItems.map(item => (
              <View key={item.id} style={styles.row}>
                <Text style={styles.name}>{item.canonical_name}</Text>
                {editingId === item.id ? (
                  <TextInput
                    style={styles.editInput}
                    value={editQty}
                    onChangeText={setEditQty}
                    keyboardType="numeric"
                    onBlur={() => commitEdit(item)}
                    autoFocus
                  />
                ) : (
                  <Pressable onPress={() => { setEditingId(item.id); setEditQty(String(item.quantity)); }}>
                    <Text style={styles.qty}>{item.quantity}{item.unit}</Text>
                  </Pressable>
                )}
                <Pressable onPress={() => confirmDelete(item)}>
                  <Text style={styles.delete}>✕</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}
      />
      <Pressable style={styles.fab} onPress={() => router.push('/(tabs)/pantry/add')}>
        <Text style={styles.fabText}>＋</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  heading: { fontSize: 24, fontWeight: '700', padding: 16 },
  groupHeader: { fontSize: 11, fontWeight: '700', color: '#888', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee' },
  name: { flex: 1, fontSize: 15 },
  qty: { fontSize: 15, color: '#2a9d8f', marginRight: 12 },
  editInput: { width: 80, borderWidth: 1, borderColor: '#2a9d8f', borderRadius: 4, padding: 4, fontSize: 15, marginRight: 12 },
  delete: { color: '#ccc', fontSize: 16 },
  fab: { position: 'absolute', bottom: 24, right: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: '#2a9d8f', justifyContent: 'center', alignItems: 'center' },
  fabText: { color: '#fff', fontSize: 28, lineHeight: 32 },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/app/(tabs)/pantry/index.tsx
git commit -m "🥫 pantry: ingredient list screen with inline quantity editing"
```

---

### Task 3: Ingredient resolution helper (mobile SQLite)

**Files:**
- Create: `mobile/src/db/ingredients.ts`

- [ ] **Step 1: Write ingredients.ts**

```typescript
// mobile/src/db/ingredients.ts
import { getDb } from './client';
import type { Ingredient } from '@/types';

// Find by canonical name (exact match). Returns null if not found.
export async function findIngredientByName(canonicalName: string): Promise<Ingredient | null> {
  const db = await getDb();
  return db.getFirstAsync<Ingredient>(
    'SELECT * FROM ingredients WHERE canonical_name = ?',
    [canonicalName.toLowerCase().trim()]
  );
}

// Find by api_ingredient_id UUID.
export async function findIngredientByApiId(apiId: string): Promise<Ingredient | null> {
  const db = await getDb();
  return db.getFirstAsync<Ingredient>(
    'SELECT * FROM ingredients WHERE api_ingredient_id = ?',
    [apiId]
  );
}

// Insert or return existing. Prefers api_ingredient_id match, falls back to canonical_name.
export async function resolveOrCreateIngredient(params: {
  canonical_name: string;
  api_ingredient_id?: string | null;
  api_name?: string | null;
  category?: string | null;
}): Promise<number> {
  const db = await getDb();
  const name = params.canonical_name.toLowerCase().trim();

  if (params.api_ingredient_id) {
    const byId = await findIngredientByApiId(params.api_ingredient_id);
    if (byId) return byId.id;
  }

  const byName = await findIngredientByName(name);
  if (byName) return byName.id;

  const result = await db.runAsync(
    `INSERT INTO ingredients (canonical_name, api_ingredient_id, api_name, category)
     VALUES (?, ?, ?, ?)`,
    [name, params.api_ingredient_id ?? null, params.api_name ?? null, params.category ?? null]
  );
  return result.lastInsertRowId;
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/ingredients.test.ts
import { resolveOrCreateIngredient } from '@/db/ingredients';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('resolveOrCreateIngredient', () => {
  it('returns existing id when ingredient found by api_ingredient_id', async () => {
    const mockDb = {
      getFirstAsync: jest.fn()
        .mockResolvedValueOnce({ id: 5, canonical_name: 'chicken breast' }),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    const id = await resolveOrCreateIngredient({
      canonical_name: 'Chicken Breast',
      api_ingredient_id: 'uuid-123',
    });

    expect(id).toBe(5);
    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });

  it('normalises name to lowercase and inserts when not found', async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue(null),
      runAsync: jest.fn().mockResolvedValue({ lastInsertRowId: 9 }),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    const id = await resolveOrCreateIngredient({ canonical_name: 'Salmon Fillet' });

    expect(id).toBe(9);
    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('INSERT INTO ingredients'),
      expect.arrayContaining(['salmon fillet'])
    );
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/ingredients.test.ts --verbose
```
Expected: 2 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/ingredients.ts mobile/src/__tests__/db/ingredients.test.ts
git commit -m "🔗 db: ingredient resolution (find/create by name or api_id)"
```

---

### Task 4: Backend — receipt scan endpoint (Textract + Claude)

**Files:**
- Create: `backend/src/glean/receipts/schemas.py`
- Create: `backend/src/glean/receipts/service.py`
- Create: `backend/src/glean/receipts/router.py`
- Create: `backend/tests/receipts/test_router.py`
- Create: `backend/tests/receipts/fixtures/receipt_textract.json`
- Create: `backend/tests/receipts/fixtures/receipt_claude.json`

- [ ] **Step 1: Write schemas.py**

```python
# backend/src/glean/receipts/schemas.py
from pydantic import BaseModel


class ParsedIngredient(BaseModel):
    name: str            # Claude-normalised canonical name
    quantity: float
    unit: str            # Normalised unit: "g", "ml", "units"
    unit_price: float | None = None   # Price per normalised unit (e.g. £/g)
    confidence: float    # 0.0–1.0; < 0.7 flagged for user review


class ScanResponse(BaseModel):
    items: list[ParsedIngredient]


class DescribeRequest(BaseModel):
    text: str
```

- [ ] **Step 2: Write test fixtures**

```json
// backend/tests/receipts/fixtures/receipt_textract.json
{
  "ExpenseDocuments": [{
    "LineItemGroups": [{
      "LineItems": [
        {
          "LineItemExpenseFields": [
            {"Type": {"Text": "ITEM"}, "ValueDetection": {"Text": "CKNBR SL 500G", "Confidence": 92.0}},
            {"Type": {"Text": "QUANTITY"}, "ValueDetection": {"Text": "1", "Confidence": 95.0}},
            {"Type": {"Text": "PRICE"}, "ValueDetection": {"Text": "3.50", "Confidence": 98.0}}
          ]
        },
        {
          "LineItemExpenseFields": [
            {"Type": {"Text": "ITEM"}, "ValueDetection": {"Text": "WHOLE MILK 2L", "Confidence": 97.0}},
            {"Type": {"Text": "QUANTITY"}, "ValueDetection": {"Text": "1", "Confidence": 99.0}},
            {"Type": {"Text": "PRICE"}, "ValueDetection": {"Text": "1.35", "Confidence": 99.0}}
          ]
        }
      ]
    }]
  }]
}
```

```json
// backend/tests/receipts/fixtures/receipt_claude.json
{
  "items": [
    {"name": "chicken breast", "quantity": 500, "unit": "g", "unit_price": 0.007, "confidence": 0.92},
    {"name": "whole milk", "quantity": 2000, "unit": "ml", "unit_price": 0.000675, "confidence": 0.97}
  ]
}
```

- [ ] **Step 3: Write service.py**

```python
# backend/src/glean/receipts/service.py
import json
import boto3
import anthropic
from glean.config import get_settings
from glean.observability import logger, tracer
from glean.receipts.schemas import ParsedIngredient, ScanResponse, DescribeRequest

NORMALISE_SYSTEM_PROMPT = """You are a grocery ingredient normaliser.
Given a list of receipt line items (name, quantity, price), return a JSON array of objects with:
- name: canonical lowercase ingredient name (e.g. "chicken breast", "whole milk")
- quantity: numeric quantity in a sensible base unit (grams for solids, ml for liquids, units for countables)
- unit: "g", "ml", or "units"
- unit_price: price per normalised unit (e.g. if 500g costs £3.50, unit_price = 3.50/500 = 0.007)
- confidence: 0.0–1.0 reflecting how certain you are about the normalisation

Respond with ONLY valid JSON. No markdown, no explanation."""


def _extract_textract_lines(textract_response: dict) -> list[dict]:
    lines = []
    for doc in textract_response.get("ExpenseDocuments", []):
        for group in doc.get("LineItemGroups", []):
            for line in group.get("LineItems", []):
                item: dict = {}
                for field in line.get("LineItemExpenseFields", []):
                    field_type = field["Type"]["Text"]
                    value = field["ValueDetection"]["Text"]
                    confidence = field["ValueDetection"]["Confidence"]
                    if field_type == "ITEM":
                        item["name"] = value
                        item["confidence"] = confidence / 100
                    elif field_type == "QUANTITY":
                        item["quantity_raw"] = value
                    elif field_type == "PRICE":
                        item["price"] = value
                if "name" in item:
                    lines.append(item)
    return lines


@tracer.capture_method
def scan_receipt(image_bytes: bytes) -> ScanResponse:
    import uuid
    s3 = boto3.client("s3", region_name=get_settings().aws_region)
    s3_key = f"receipts/tmp/{uuid.uuid4()}.jpg"
    logger.info("uploading receipt to s3", extra={"key": s3_key, "bytes": len(image_bytes)})
    s3.put_object(Bucket=get_settings().s3_receipts_bucket, Key=s3_key, Body=image_bytes)

    textract = boto3.client("textract", region_name=get_settings().aws_region)
    try:
        textract_response = textract.analyze_expense(
            Document={"S3Object": {"Bucket": get_settings().s3_receipts_bucket, "Name": s3_key}}
        )
        lines = _extract_textract_lines(textract_response)
        logger.info("textract extracted lines", extra={"count": len(lines)})
    finally:
        s3.delete_object(Bucket=get_settings().s3_receipts_bucket, Key=s3_key)

    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=NORMALISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(lines)}],
    )
    raw = message.content[0].text
    logger.info("claude normalised items", extra={"tokens": message.usage.input_tokens})

    items = [ParsedIngredient(**item) for item in json.loads(raw)]
    return ScanResponse(items=items)


@tracer.capture_method
def describe_purchase(request: DescribeRequest) -> ScanResponse:
    client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=NORMALISE_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Parse this grocery purchase description: {request.text}"
        }],
    )
    raw = message.content[0].text
    items = [ParsedIngredient(**item) for item in json.loads(raw)]
    return ScanResponse(items=items)
```

- [ ] **Step 4: Write router.py**

```python
# backend/src/glean/receipts/router.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from glean.dependencies import verify_cognito_token
from glean.receipts.schemas import ScanResponse, DescribeRequest
from glean.receipts import service

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/scan", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
async def scan_receipt(file: UploadFile = File(...)) -> ScanResponse:
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only image/jpeg and image/png are accepted")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 10MB")
    return service.scan_receipt(image_bytes)


@router.post("/describe", response_model=ScanResponse, dependencies=[Depends(verify_cognito_token)])
def describe_purchase(request: DescribeRequest) -> ScanResponse:
    return service.describe_purchase(request)
```

- [ ] **Step 5: Register router in main.py**

```python
# backend/src/glean/main.py  (add after existing imports)
from glean.receipts.router import router as receipts_router

app.include_router(receipts_router)
```

- [ ] **Step 6: Write conftest.py**

```python
# backend/tests/conftest.py
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
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
```

- [ ] **Step 7: Write tests**

```python
# backend/tests/receipts/test_router.py
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_textract_response() -> dict:
    return json.loads((FIXTURES / "receipt_textract.json").read_text())


def _mock_claude_response() -> list[dict]:
    return json.loads((FIXTURES / "receipt_claude.json").read_text())["items"]


def test_scan_receipt_returns_parsed_items(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    mock_s3 = MagicMock()
    mock_textract = MagicMock()
    mock_textract.analyze_expense.return_value = _mock_textract_response()

    mock_claude_content = MagicMock()
    mock_claude_content.text = json.dumps(_mock_claude_response())
    mock_claude_msg = MagicMock()
    mock_claude_msg.content = [mock_claude_content]
    mock_claude_msg.usage.input_tokens = 120

    def boto3_client_factory(service_name: str, **kwargs):
        if service_name == "s3":
            return mock_s3
        return mock_textract

    with patch("boto3.client", side_effect=boto3_client_factory), \
         patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_claude_msg
        response = client.post(
            "/receipts/scan",
            headers=auth_headers,
            files={"file": ("receipt.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["name"] == "chicken breast"
    assert items[0]["quantity"] == 500
    assert items[0]["unit"] == "g"
    assert items[0]["unit_price"] == pytest.approx(0.007)
    mock_s3.put_object.assert_called_once()
    mock_s3.delete_object.assert_called_once()


def test_scan_receipt_requires_auth(client: TestClient) -> None:
    response = client.post("/receipts/scan", files={"file": ("r.jpg", b"x", "image/jpeg")})
    assert response.status_code == 401


def test_scan_receipt_rejects_non_image(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/receipts/scan",
        headers=auth_headers,
        files={"file": ("data.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "image/jpeg" in response.json()["detail"]


def test_scan_receipt_rejects_oversized(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    oversized_bytes = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/receipts/scan",
        headers=auth_headers,
        files={"file": ("big.jpg", oversized_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "10MB" in response.json()["detail"]


def test_describe_purchase_parses_text(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    mock_claude_content = MagicMock()
    mock_claude_content.text = json.dumps(_mock_claude_response())
    mock_claude_msg = MagicMock()
    mock_claude_msg.content = [mock_claude_content]
    mock_claude_msg.usage.input_tokens = 80

    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = mock_claude_msg
        response = client.post(
            "/receipts/describe",
            headers=auth_headers,
            json={"text": "I bought a kilo of chicken and 2 litres of milk"},
        )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
```

- [ ] **Step 8: Run tests**

```bash
cd backend && uv run pytest tests/receipts/ -v
```
Expected: 5 passing

- [ ] **Step 9: Commit**

```bash
git add backend/src/glean/receipts/ backend/tests/receipts/ backend/tests/conftest.py
git commit -m "🧾 receipts: Textract S3-buffered scan, Cognito auth, content-type + size validation"
```

---

### Task 5: Unit normalization service (on-device)

**Files:**
- Create: `mobile/src/normalization/units.ts`
- Create: `mobile/src/__tests__/normalization/units.test.ts`

- [ ] **Step 1: Write units.ts**

```typescript
// mobile/src/normalization/units.ts

// Deterministic lookup: source_unit → { factor to apply, target unit }
const UNIT_CONVERSIONS: Record<string, { factor: number; to: string }> = {
  // Volume → ml
  l: { factor: 1000, to: 'ml' },
  litre: { factor: 1000, to: 'ml' },
  litres: { factor: 1000, to: 'ml' },
  liter: { factor: 1000, to: 'ml' },
  liters: { factor: 1000, to: 'ml' },
  tsp: { factor: 4.92892, to: 'ml' },
  teaspoon: { factor: 4.92892, to: 'ml' },
  teaspoons: { factor: 4.92892, to: 'ml' },
  tbsp: { factor: 14.7868, to: 'ml' },
  tablespoon: { factor: 14.7868, to: 'ml' },
  tablespoons: { factor: 14.7868, to: 'ml' },
  'fl oz': { factor: 29.5735, to: 'ml' },
  cup: { factor: 236.588, to: 'ml' },
  cups: { factor: 236.588, to: 'ml' },
  pint: { factor: 473.176, to: 'ml' },
  pints: { factor: 473.176, to: 'ml' },
  // Mass → g
  kg: { factor: 1000, to: 'g' },
  kilogram: { factor: 1000, to: 'g' },
  kilograms: { factor: 1000, to: 'g' },
  oz: { factor: 28.3495, to: 'g' },
  ounce: { factor: 28.3495, to: 'g' },
  ounces: { factor: 28.3495, to: 'g' },
  lb: { factor: 453.592, to: 'g' },
  lbs: { factor: 453.592, to: 'g' },
  pound: { factor: 453.592, to: 'g' },
  pounds: { factor: 453.592, to: 'g' },
};

// Density table (g per ml) for volume→mass conversions when canonical_unit is 'g'.
// Keyed by canonical_name (lowercase).
const INGREDIENT_DENSITY: Record<string, number> = {
  'plain flour': 0.593,
  'bread flour': 0.593,
  'self-raising flour': 0.593,
  'caster sugar': 0.845,
  'granulated sugar': 0.845,
  'icing sugar': 0.561,
  'brown sugar': 0.845,
  'cocoa powder': 0.469,
  'baking soda': 1.08,
  'baking powder': 0.9,
  rice: 0.888,
  oats: 0.41,
  'rolled oats': 0.41,
  honey: 1.42,
  'maple syrup': 1.32,
  milk: 1.03,
  cream: 1.01,
  water: 1.0,
};

export interface NormalizeResult {
  quantity: number;
  unit: string;
  source: 'identity' | 'lookup' | 'density';
}

/**
 * Deterministically normalise quantity+unit to the ingredient's canonical_unit.
 * Returns null if the conversion cannot be resolved without Claude (caller handles).
 *
 * Invoked at three points:
 *   (a) receipt confirm before pantry upsert
 *   (b) recipe import before saving ingredient quantities
 *   (c) pantry decrement before quantity subtraction
 */
export function normalizeUnit(params: {
  quantity: number;
  unit: string;
  canonicalUnit: string | null;
  canonicalName: string;
}): NormalizeResult | null {
  const { quantity, canonicalUnit, canonicalName } = params;
  const unit = params.unit.toLowerCase().trim();

  // No canonical unit set, or already in canonical unit
  if (!canonicalUnit || unit === canonicalUnit) {
    return { quantity, unit: canonicalUnit ?? unit, source: 'identity' };
  }

  const conv = UNIT_CONVERSIONS[unit];
  if (conv) {
    if (conv.to === canonicalUnit) {
      // Direct conversion (e.g. kg → g, L → ml)
      return { quantity: quantity * conv.factor, unit: canonicalUnit, source: 'lookup' };
    }
    // Volume → mass via density (conv.to === 'ml', canonicalUnit === 'g')
    if (conv.to === 'ml' && canonicalUnit === 'g') {
      const density = INGREDIENT_DENSITY[canonicalName.toLowerCase()];
      if (density !== undefined) {
        return { quantity: quantity * conv.factor * density, unit: 'g', source: 'density' };
      }
    }
    // Mass → volume via density (conv.to === 'g', canonicalUnit === 'ml')
    if (conv.to === 'g' && canonicalUnit === 'ml') {
      const density = INGREDIENT_DENSITY[canonicalName.toLowerCase()];
      if (density !== undefined) {
        return { quantity: (quantity * conv.factor) / density, unit: 'ml', source: 'density' };
      }
    }
  }

  // Cannot normalize deterministically — caller should accept original value or escalate
  return null;
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/normalization/units.test.ts
import { normalizeUnit } from '@/normalization/units';

describe('normalizeUnit', () => {
  it('returns identity when unit matches canonical_unit', () => {
    const result = normalizeUnit({ quantity: 500, unit: 'g', canonicalUnit: 'g', canonicalName: 'chicken breast' });
    expect(result).toEqual({ quantity: 500, unit: 'g', source: 'identity' });
  });

  it('returns identity when canonical_unit is null', () => {
    const result = normalizeUnit({ quantity: 2, unit: 'units', canonicalUnit: null, canonicalName: 'egg' });
    expect(result).toEqual({ quantity: 2, unit: 'units', source: 'identity' });
  });

  it('converts kg → g', () => {
    const result = normalizeUnit({ quantity: 0.5, unit: 'kg', canonicalUnit: 'g', canonicalName: 'beef mince' });
    expect(result?.quantity).toBeCloseTo(500, 1);
    expect(result?.unit).toBe('g');
    expect(result?.source).toBe('lookup');
  });

  it('converts L → ml', () => {
    const result = normalizeUnit({ quantity: 1.5, unit: 'l', canonicalUnit: 'ml', canonicalName: 'whole milk' });
    expect(result?.quantity).toBeCloseTo(1500, 1);
    expect(result?.unit).toBe('ml');
    expect(result?.source).toBe('lookup');
  });

  it('converts cup of flour → g via density', () => {
    const result = normalizeUnit({ quantity: 1, unit: 'cup', canonicalUnit: 'g', canonicalName: 'plain flour' });
    // 1 cup = 236.588ml × 0.593 g/ml ≈ 140.3g
    expect(result?.quantity).toBeCloseTo(140.3, 0);
    expect(result?.unit).toBe('g');
    expect(result?.source).toBe('density');
  });

  it('returns null for unknown ambiguous conversion', () => {
    const result = normalizeUnit({ quantity: 1, unit: 'head', canonicalUnit: 'units', canonicalName: 'garlic' });
    expect(result).toBeNull();
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/normalization/units.test.ts --verbose
```
Expected: 6 passing

- [ ] **Step 4: Invoke normalization in receipt confirm**

In `mobile/app/(tabs)/pantry/review.tsx` inside the `confirm()` function, after resolving each ingredient, call `normalizeUnit` before `upsertPantryItem`. Import `normalizeUnit` from `@/normalization/units` and `findIngredientByName` from `@/db/ingredients` to get the ingredient's `canonical_unit`.

The confirm loop becomes:
```typescript
for (const item of confirmedItems) {
  const ingredientId = await resolveOrCreateIngredient({ canonical_name: item.name });
  const ingredient = await db.getFirstAsync<{ canonical_unit: string | null }>(
    'SELECT canonical_unit FROM ingredients WHERE id = ?', [ingredientId]
  );
  const normalized = normalizeUnit({
    quantity: item.quantity,
    unit: item.unit,
    canonicalUnit: ingredient?.canonical_unit ?? null,
    canonicalName: item.name,
  });
  await upsertPantryItem({
    ingredient_id: ingredientId,
    quantity: normalized?.quantity ?? item.quantity,
    unit: normalized?.unit ?? item.unit,
    unit_price: item.unit_price ?? null,
  });
  resolvedIds.push(ingredientId);
}
```

- [ ] **Step 5: Commit**

```bash
git add mobile/src/normalization/ mobile/src/__tests__/normalization/ mobile/app/\(tabs\)/pantry/review.tsx
git commit -m "📐 normalization: on-device unit normalization service with density table"
```

---

### Task 6: Mobile — shared review/confirm screen

**Files:**
- Create: `mobile/app/(tabs)/pantry/review.tsx`
- Create: `mobile/src/db/shopping.ts` (partial — just the cross-check query)

- [ ] **Step 1: Write shopping.ts cross-check function**

```typescript
// mobile/src/db/shopping.ts
import { getDb } from './client';

// Mark shopping list items as checked if they match any of the given ingredient_ids.
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

- [ ] **Step 2: Write review.tsx**

```typescript
// mobile/app/(tabs)/pantry/review.tsx
import { useState } from 'react';
import { View, Text, FlatList, Pressable, TextInput, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { resolveOrCreateIngredient } from '@/db/ingredients';
import { upsertPantryItem } from '@/db/pantry';
import { checkOffByIngredientIds } from '@/db/shopping';

interface ReviewItem {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  confidence: number;
  // Populated after resolution
  ingredient_id?: number;
}

export default function ReviewScreen() {
  const params = useLocalSearchParams<{ items: string }>();
  const [items, setItems] = useState<ReviewItem[]>(
    JSON.parse(params.items ?? '[]')
  );
  const [saving, setSaving] = useState(false);

  function updateItem(index: number, patch: Partial<ReviewItem>) {
    setItems(prev => prev.map((item, i) => i === index ? { ...item, ...patch } : item));
  }

  function removeItem(index: number) {
    setItems(prev => prev.filter((_, i) => i !== index));
  }

  async function confirm() {
    setSaving(true);
    try {
      const resolvedIds: number[] = [];
      for (const item of items) {
        const ingredientId = await resolveOrCreateIngredient({ canonical_name: item.name });
        await upsertPantryItem({
          ingredient_id: ingredientId,
          quantity: item.quantity,
          unit: item.unit,
          unit_price: item.unit_price,
        });
        resolvedIds.push(ingredientId);
      }
      await checkOffByIngredientIds(resolvedIds);
      router.replace('/(tabs)/pantry');
    } catch (e) {
      Alert.alert('Error', 'Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Review Items</Text>
      <Text style={styles.subtitle}>Edit or remove any items before confirming.</Text>
      <FlatList
        data={items}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item, index }) => (
          <View style={[styles.row, item.confidence < 0.7 && styles.flagged]}>
            {item.confidence < 0.7 && <Text style={styles.flag}>⚠ Check</Text>}
            <TextInput
              style={styles.nameInput}
              value={item.name}
              onChangeText={v => updateItem(index, { name: v })}
            />
            <TextInput
              style={styles.qtyInput}
              value={String(item.quantity)}
              onChangeText={v => updateItem(index, { quantity: parseFloat(v) || 0 })}
              keyboardType="numeric"
            />
            <Text style={styles.unit}>{item.unit}</Text>
            <Pressable onPress={() => removeItem(index)}>
              <Text style={styles.remove}>✕</Text>
            </Pressable>
          </View>
        )}
      />
      <Pressable style={styles.confirmButton} onPress={confirm} disabled={saving}>
        {saving
          ? <ActivityIndicator color="#fff" />
          : <Text style={styles.confirmText}>Confirm {items.length} item{items.length !== 1 ? 's' : ''}</Text>
        }
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  heading: { fontSize: 22, fontWeight: '700', padding: 16 },
  subtitle: { fontSize: 13, color: '#888', paddingHorizontal: 16, paddingBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee' },
  flagged: { backgroundColor: '#fff8f0' },
  flag: { color: '#f7a04a', fontSize: 11, marginRight: 6 },
  nameInput: { flex: 1, fontSize: 14, borderBottomWidth: 1, borderColor: '#ddd', marginRight: 8 },
  qtyInput: { width: 60, fontSize: 14, borderBottomWidth: 1, borderColor: '#ddd', marginRight: 4, textAlign: 'right' },
  unit: { fontSize: 12, color: '#888', width: 30, marginRight: 8 },
  remove: { color: '#ccc', fontSize: 16 },
  confirmButton: { margin: 16, backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center' },
  confirmText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
```

- [ ] **Step 3: Write test for checkOffByIngredientIds**

```typescript
// mobile/src/__tests__/db/shopping.test.ts
import { checkOffByIngredientIds } from '@/db/shopping';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('checkOffByIngredientIds', () => {
  it('marks matching shopping list items as checked', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await checkOffByIngredientIds([1, 3, 5]);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining('UPDATE shopping_list_items SET is_checked = 1'),
      [1, 3, 5]
    );
  });

  it('does nothing when passed empty array', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await checkOffByIngredientIds([]);

    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 4: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/shopping.test.ts --verbose
```
Expected: 2 passing

- [ ] **Step 5: Commit**

```bash
git add mobile/app/(tabs)/pantry/review.tsx mobile/src/db/shopping.ts mobile/src/__tests__/db/shopping.test.ts
git commit -m "📋 pantry: shared review/confirm screen with shopping list cross-check"
```

---

### Task 7: Mobile — receipt scan screen

**Files:**
- Create: `mobile/app/(tabs)/pantry/scan.tsx`

- [ ] **Step 1: Write scan.tsx**

```typescript
// mobile/app/(tabs)/pantry/scan.tsx
import { useState, useRef } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router } from 'expo-router';
import { apiClient } from '@/api/client';
import type { ScanResponse } from '@/types';

// Extend types with backend ScanResponse shape
declare module '@/types' {
  interface ScanResponse {
    items: Array<{ name: string; quantity: number; unit: string; unit_price: number | null; confidence: number }>;
  }
}

export default function ScanScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const cameraRef = useRef<CameraView>(null);

  if (!permission) return <View style={{ flex: 1 }} />;
  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={styles.message}>Camera permission is needed to scan receipts.</Text>
        <Pressable style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  async function capture() {
    if (!cameraRef.current || scanning) return;
    setScanning(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.8 });
      if (!photo?.base64) throw new Error('No image captured');

      const blob = await (await fetch(`data:image/jpeg;base64,${photo.base64}`)).blob();
      const form = new FormData();
      form.append('file', blob, 'receipt.jpg');

      const result = await apiClient.post<{ items: unknown[] }>('/receipts/scan', form);
      router.push({
        pathname: '/(tabs)/pantry/review',
        params: { items: JSON.stringify(result.items) },
      });
    } catch (e) {
      Alert.alert('Scan failed', 'Could not process receipt. Try again or add items manually.');
    } finally {
      setScanning(false);
    }
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back" />
      <View style={styles.controls}>
        {scanning
          ? <ActivityIndicator size="large" color="#fff" />
          : (
            <Pressable style={styles.shutterButton} onPress={capture}>
              <View style={styles.shutterInner} />
            </Pressable>
          )
        }
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  message: { color: '#fff', textAlign: 'center', margin: 24, fontSize: 16 },
  button: { margin: 24, backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600' },
  camera: { flex: 1 },
  controls: { position: 'absolute', bottom: 40, width: '100%', alignItems: 'center' },
  shutterButton: { width: 72, height: 72, borderRadius: 36, backgroundColor: 'rgba(255,255,255,0.3)', justifyContent: 'center', alignItems: 'center' },
  shutterInner: { width: 58, height: 58, borderRadius: 29, backgroundColor: '#fff' },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/app/(tabs)/pantry/scan.tsx
git commit -m "📸 pantry: receipt camera scan screen"
```

---

### Task 8: Mobile — NL describe + manual entry screens + FAB

**Files:**
- Create: `mobile/app/(tabs)/pantry/describe.tsx`
- Create: `mobile/app/(tabs)/pantry/manual-entry.tsx`
- Create: `mobile/app/(tabs)/pantry/add.tsx`

- [ ] **Step 1: Write describe.tsx**

```typescript
// mobile/app/(tabs)/pantry/describe.tsx
import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { router } from 'expo-router';
import { apiClient } from '@/api/client';

export default function DescribeScreen() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);

  async function parse() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const result = await apiClient.post<{ items: unknown[] }>('/receipts/describe', { text });
      router.push({
        pathname: '/(tabs)/pantry/review',
        params: { items: JSON.stringify(result.items) },
      });
    } catch {
      Alert.alert('Parse failed', 'Could not understand that. Try being more specific, e.g. "500g chicken breast, 2 tins tomatoes".');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Describe your shop</Text>
      <Text style={styles.subtitle}>e.g. "I bought a kilo of mince and two tins of tomatoes"</Text>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder="What did you buy?"
        multiline
        autoFocus
      />
      <Pressable style={styles.button} onPress={parse} disabled={loading || !text.trim()}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Parse →</Text>}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#fff' },
  heading: { fontSize: 22, fontWeight: '700', marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#888', marginBottom: 20 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 12, fontSize: 16, minHeight: 100, textAlignVertical: 'top', marginBottom: 16 },
  button: { backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
```

- [ ] **Step 2: Write manual-entry.tsx**

```typescript
// mobile/app/(tabs)/pantry/manual-entry.tsx
import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Alert } from 'react-native';
import { router } from 'expo-router';
import { resolveOrCreateIngredient } from '@/db/ingredients';
import { upsertPantryItem } from '@/db/pantry';

const UNITS = ['g', 'ml', 'units', 'kg', 'l'];

export default function ManualEntryScreen() {
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('g');
  const [saving, setSaving] = useState(false);

  async function save() {
    const qty = parseFloat(quantity);
    if (!name.trim() || isNaN(qty) || qty <= 0) {
      Alert.alert('Please enter a name and valid quantity.');
      return;
    }
    setSaving(true);
    try {
      const ingredientId = await resolveOrCreateIngredient({ canonical_name: name.trim().toLowerCase() });
      await upsertPantryItem({ ingredient_id: ingredientId, quantity: qty, unit });
      router.replace('/(tabs)/pantry');
    } catch {
      Alert.alert('Failed to save item.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Add item</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Ingredient name" autoFocus />
      <View style={styles.row}>
        <TextInput style={[styles.input, { flex: 1, marginRight: 8 }]} value={quantity} onChangeText={setQuantity} placeholder="Quantity" keyboardType="numeric" />
        <View style={styles.unitRow}>
          {UNITS.map(u => (
            <Pressable key={u} style={[styles.unitBtn, unit === u && styles.unitBtnActive]} onPress={() => setUnit(u)}>
              <Text style={unit === u ? styles.unitTextActive : styles.unitText}>{u}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      <Pressable style={styles.button} onPress={save} disabled={saving}>
        <Text style={styles.buttonText}>Add to Pantry</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#fff' },
  heading: { fontSize: 22, fontWeight: '700', marginBottom: 20 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 12, fontSize: 16, marginBottom: 12 },
  row: { flexDirection: 'row', marginBottom: 12 },
  unitRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  unitBtn: { borderWidth: 1, borderColor: '#ddd', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 },
  unitBtnActive: { borderColor: '#2a9d8f', backgroundColor: '#2a9d8f' },
  unitText: { color: '#444', fontSize: 13 },
  unitTextActive: { color: '#fff', fontSize: 13 },
  button: { backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center', marginTop: 8 },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
```

- [ ] **Step 3: Write add.tsx (FAB action sheet)**

```typescript
// mobile/app/(tabs)/pantry/add.tsx
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { router } from 'expo-router';

export default function AddScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Add to Pantry</Text>
      <Pressable style={styles.option} onPress={() => router.replace('/(tabs)/pantry/scan')}>
        <Text style={styles.icon}>🧾</Text>
        <View>
          <Text style={styles.label}>Scan Receipt</Text>
          <Text style={styles.sub}>Take a photo of your receipt</Text>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.replace('/(tabs)/pantry/describe')}>
        <Text style={styles.icon}>💬</Text>
        <View>
          <Text style={styles.label}>Describe Purchase</Text>
          <Text style={styles.sub}>Type what you bought</Text>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.replace('/(tabs)/pantry/manual-entry')}>
        <Text style={styles.icon}>✏️</Text>
        <View>
          <Text style={styles.label}>Manual Entry</Text>
          <Text style={styles.sub}>Add a single item</Text>
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#fff' },
  heading: { fontSize: 22, fontWeight: '700', marginBottom: 24 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 16, padding: 16, borderWidth: 1, borderColor: '#eee', borderRadius: 12, marginBottom: 12 },
  icon: { fontSize: 28 },
  label: { fontSize: 16, fontWeight: '600', marginBottom: 2 },
  sub: { fontSize: 13, color: '#888' },
});
```

- [ ] **Step 4: Commit**

```bash
git add mobile/app/(tabs)/pantry/
git commit -m "📦 pantry: describe, manual entry, and add action screens"
```
