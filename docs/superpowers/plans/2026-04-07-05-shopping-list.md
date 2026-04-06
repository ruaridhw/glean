# Shopping List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Shop tab — shopping list display, manual item addition, individual check-off, and the "Completed checkout" flow. Also complete the Settings screen with all configurable user preferences.

**Architecture:** `shopping_list_items` is the single source of truth. Items come from two sources: auto-generated meal plan gaps (added in Plan 4) and manual additions. "Completed checkout" marks the session boundary — unchecked items persist for the next trip. The Settings screen reads/writes `user_config` via the existing `getUserConfig` / `updateUserConfig` functions.

**Tech Stack:** expo-sqlite, Jest + React Native Testing Library

**Depends on:** Plan 1 (Foundation), Plan 2 (Pantry — `checkOffByIngredientIds`), Plan 4 (Meal Planning — `addShoppingGapsForRecipe`, `getShoppingListItems`).

---

## File Structure

```
mobile/
  app/(tabs)/
    shop/
      index.tsx              # Shopping list screen
    settings/
      index.tsx              # Settings screen (full implementation)
  src/db/
    shopping.ts              # Extended: manual add, toggle check, clear checked
```

---

### Task 1: Complete shopping.ts queries

**Files:**
- Modify: `mobile/src/db/shopping.ts`

- [ ] **Step 1: Append remaining shopping queries**

```typescript
// Append to mobile/src/db/shopping.ts

export async function addManualShoppingItem(params: {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  ingredient_id?: number | null;
}): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    `INSERT INTO shopping_list_items (ingredient_id, name, quantity, unit, source)
     VALUES (?, ?, ?, ?, 'manual')`,
    [params.ingredient_id ?? null, params.name, params.quantity ?? null, params.unit ?? null]
  );
}

export async function toggleShoppingItem(id: number, checked: boolean): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    'UPDATE shopping_list_items SET is_checked = ? WHERE id = ?',
    [checked ? 1 : 0, id]
  );
}

export async function deleteShoppingItem(id: number): Promise<void> {
  const db = await getDb();
  await db.runAsync('DELETE FROM shopping_list_items WHERE id = ?', [id]);
}

// "Completed checkout" — deletes all checked items, leaves unchecked intact.
export async function completeCheckout(): Promise<void> {
  const db = await getDb();
  await db.runAsync('DELETE FROM shopping_list_items WHERE is_checked = 1');
}
```

- [ ] **Step 2: Write tests**

```typescript
// mobile/src/__tests__/db/shopping-complete.test.ts
import { completeCheckout, toggleShoppingItem, addManualShoppingItem } from '@/db/shopping';
import { getDb } from '@/db/client';

jest.mock('@/db/client');

describe('completeCheckout', () => {
  it('deletes only checked items', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await completeCheckout();

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      'DELETE FROM shopping_list_items WHERE is_checked = 1'
    );
  });
});

describe('toggleShoppingItem', () => {
  it('sets is_checked to 1 when checked = true', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await toggleShoppingItem(5, true);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      'UPDATE shopping_list_items SET is_checked = ? WHERE id = ?',
      [1, 5]
    );
  });

  it('sets is_checked to 0 when checked = false', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await toggleShoppingItem(5, false);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      'UPDATE shopping_list_items SET is_checked = ? WHERE id = ?',
      [0, 5]
    );
  });
});

describe('addManualShoppingItem', () => {
  it('inserts with source = manual', async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await addManualShoppingItem({ name: 'birthday candles', quantity: null, unit: null });

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("'manual'"),
      expect.arrayContaining(['birthday candles'])
    );
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd mobile && npx jest src/__tests__/db/shopping-complete.test.ts --verbose
```
Expected: 4 passing

- [ ] **Step 4: Commit**

```bash
git add mobile/src/db/shopping.ts mobile/src/__tests__/db/shopping-complete.test.ts
git commit -m "🛒 db: complete shopping list queries (toggle, add, checkout)"
```

---

### Task 2: Shop screen

**Files:**
- Modify: `mobile/app/(tabs)/shop/index.tsx`

- [ ] **Step 1: Write shop/index.tsx**

```typescript
// mobile/app/(tabs)/shop/index.tsx
import { useState, useCallback } from 'react';
import {
  View, Text, FlatList, Pressable, TextInput,
  StyleSheet, ActivityIndicator, Alert
} from 'react-native';
import { useFocusEffect, router } from 'expo-router';
import {
  getShoppingListItems,
  addManualShoppingItem,
  toggleShoppingItem,
  deleteShoppingItem,
  completeCheckout,
} from '@/db/shopping';
import type { ShoppingListItem } from '@/db/shopping';

export default function ShopScreen() {
  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newItemName, setNewItemName] = useState('');
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setItems(await getShoppingListItems());
    setLoading(false);
  }, []);

  useFocusEffect(load);

  async function handleAdd() {
    if (!newItemName.trim()) return;
    setAdding(true);
    await addManualShoppingItem({ name: newItemName.trim() });
    setNewItemName('');
    setAdding(false);
    await load();
  }

  async function handleToggle(item: ShoppingListItem) {
    await toggleShoppingItem(item.id, !item.is_checked);
    await load();
  }

  async function handleDelete(item: ShoppingListItem) {
    await deleteShoppingItem(item.id);
    await load();
  }

  function handleCompleteCheckout() {
    const checkedCount = items.filter(i => i.is_checked).length;
    const uncheckedCount = items.filter(i => !i.is_checked).length;

    Alert.alert(
      'Completed checkout',
      'Did you get a receipt? Scanning it will update your pantry automatically.',
      [
        {
          text: 'Scan receipt',
          onPress: () => {
            // Navigate to receipt scan flow. On confirm, pantry updates + shopping list cross-check
            // happen automatically via review.tsx. Then completeCheckout removes checked items.
            router.push('/(tabs)/pantry/scan?returnTo=shop');
          },
        },
        {
          text: 'Skip — just clear checked',
          onPress: () => {
            Alert.alert(
              'Clear checked items?',
              `${checkedCount} checked item${checkedCount !== 1 ? 's' : ''} will be removed.${
                uncheckedCount > 0
                  ? `\n\n${uncheckedCount} unchecked item${uncheckedCount !== 1 ? 's' : ''} will remain for next time.`
                  : ''
              }`,
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Clear',
                  onPress: async () => {
                    await completeCheckout();
                    await load();
                  },
                },
              ]
            );
          },
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  }

  const unchecked = items.filter(i => !i.is_checked);
  const checked = items.filter(i => i.is_checked);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.heading}>Shopping List</Text>
        {checked.length > 0 && (
          <Pressable style={styles.checkoutBtn} onPress={handleCompleteCheckout}>
            <Text style={styles.checkoutBtnText}>Completed checkout</Text>
          </Pressable>
        )}
      </View>

      <FlatList
        data={[...unchecked, ...checked]}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => (
          <View style={[styles.itemRow, item.is_checked && styles.checkedRow]}>
            <Pressable style={styles.checkbox} onPress={() => handleToggle(item)}>
              <Text style={styles.checkboxText}>{item.is_checked ? '☑' : '☐'}</Text>
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={[styles.itemName, item.is_checked && styles.checkedText]}>
                {item.name}
              </Text>
              {item.quantity && (
                <Text style={styles.itemQty}>{item.quantity}{item.unit}</Text>
              )}
            </View>
            <View style={styles.sourceTag}>
              <Text style={styles.sourceTagText}>{item.source}</Text>
            </View>
            <Pressable onPress={() => handleDelete(item)}>
              <Text style={styles.deleteText}>✕</Text>
            </Pressable>
          </View>
        )}
        ListFooterComponent={
          <View style={styles.addRow}>
            <TextInput
              style={styles.addInput}
              value={newItemName}
              onChangeText={setNewItemName}
              placeholder="Add item…"
              returnKeyType="done"
              onSubmitEditing={handleAdd}
            />
            <Pressable style={styles.addBtn} onPress={handleAdd} disabled={adding || !newItemName.trim()}>
              <Text style={styles.addBtnText}>Add</Text>
            </Pressable>
          </View>
        }
        ListEmptyComponent={
          <Text style={styles.empty}>Your shopping list is empty.</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16 },
  heading: { fontSize: 24, fontWeight: '700' },
  checkoutBtn: { backgroundColor: '#2a9d8f', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 7 },
  checkoutBtnText: { color: '#fff', fontWeight: '600', fontSize: 13 },
  itemRow: { flexDirection: 'row', alignItems: 'center', padding: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#eee', gap: 10 },
  checkedRow: { opacity: 0.5 },
  checkbox: { width: 24 },
  checkboxText: { fontSize: 20 },
  itemName: { fontSize: 15 },
  checkedText: { textDecorationLine: 'line-through' },
  itemQty: { fontSize: 12, color: '#888', marginTop: 1 },
  sourceTag: { backgroundColor: '#f5f5f5', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  sourceTagText: { fontSize: 10, color: '#888' },
  deleteText: { color: '#ddd', fontSize: 16 },
  addRow: { flexDirection: 'row', gap: 8, padding: 16, borderTopWidth: 1, borderColor: '#eee' },
  addInput: { flex: 1, borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, fontSize: 15 },
  addBtn: { backgroundColor: '#2a9d8f', borderRadius: 8, paddingHorizontal: 16, justifyContent: 'center' },
  addBtnText: { color: '#fff', fontWeight: '600' },
  empty: { textAlign: 'center', color: '#888', marginTop: 40, fontSize: 14 },
});
```

- [ ] **Step 2: Commit**

```bash
git add mobile/app/(tabs)/shop/index.tsx
git commit -m "🛒 shop: shopping list screen with check-off and completed checkout"
```

---

### Task 3: Settings screen

**Files:**
- Modify: `mobile/app/(tabs)/settings/index.tsx`

- [ ] **Step 1: Write full settings/index.tsx**

```typescript
// mobile/app/(tabs)/settings/index.tsx
import { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, Pressable, StyleSheet,
  Alert, Switch, TextInput
} from 'react-native';
import Slider from '@react-native-community/slider';
import * as FileSystem from 'expo-file-system';
import { getUserConfig, updateUserConfig } from '@/db/config';
import { apiClient } from '@/api/client';
import { signOut } from '@/auth/cognito';
import { router } from 'expo-router';

const DIETARY_FLAGS = ['Vegetarian', 'Vegan', 'Gluten-Free', 'Dairy-Free', 'Nut-Free', 'Keto', 'Paleo'];

export default function SettingsScreen() {
  const [tolerance, setTolerance] = useState(0.5);
  const [servings, setServings] = useState('2');
  const [mealsPerWeek, setMealsPerWeek] = useState('5');
  const [dietaryFlags, setDietaryFlags] = useState<string[]>([]);
  const [maxTime, setMaxTime] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const config = await getUserConfig();
      setTolerance(config.purchase_tolerance);
      setServings(String(config.preferred_servings));
      setMealsPerWeek(String(config.meals_per_week));
      setDietaryFlags(config.dietary_flags);
      setMaxTime(config.max_active_time_mins ? String(config.max_active_time_mins) : '');
      setLoading(false);
    }
    load();
  }, []);

  async function save() {
    await updateUserConfig({
      purchase_tolerance: tolerance,
      preferred_servings: parseInt(servings, 10) || 2,
      meals_per_week: parseInt(mealsPerWeek, 10) || 5,
      dietary_flags: dietaryFlags,
      max_active_time_mins: maxTime ? parseInt(maxTime, 10) : null,
    });
    Alert.alert('Saved');
  }

  function toggleFlag(flag: string) {
    setDietaryFlags(prev =>
      prev.includes(flag) ? prev.filter(f => f !== flag) : [...prev, flag]
    );
  }

  async function exportDb() {
    const dbPath = `${FileSystem.documentDirectory}SQLite/glean.db`;
    const info = await FileSystem.getInfoAsync(dbPath);
    if (!info.exists) { Alert.alert('No database found'); return; }

    const formData = new FormData();
    formData.append('file', {
      uri: dbPath,
      name: 'glean.db',
      type: 'application/octet-stream',
    } as any);

    try {
      await apiClient.postForm('/dev/export-db', formData);
      Alert.alert('Exported', 'Database uploaded to S3 for debugging.');
    } catch (e) {
      Alert.alert('Export failed', 'Could not upload database. Check your connection.');
    }
  }

  async function handleSignOut() {
    Alert.alert('Sign out', 'You will need to sign in again to use AI features.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        style: 'destructive',
        onPress: async () => {
          await signOut();
          router.replace('/sign-in');
        },
      },
    ]);
  }

  if (loading) return null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.heading}>Settings</Text>

      <Text style={styles.sectionHeading}>Purchase Tolerance</Text>
      <Text style={styles.description}>
        {tolerance <= 0.2 ? 'Strict: pantry ingredients only' :
         tolerance <= 0.5 ? 'Moderate: minor shopping OK' :
         'Open: happy to buy new ingredients'}
      </Text>
      <Slider
        style={{ height: 40 }}
        minimumValue={0}
        maximumValue={1}
        step={0.1}
        value={tolerance}
        onValueChange={setTolerance}
        minimumTrackTintColor="#2a9d8f"
        thumbTintColor="#2a9d8f"
      />

      <Text style={styles.sectionHeading}>Meals per Week</Text>
      <TextInput style={styles.input} value={mealsPerWeek} onChangeText={setMealsPerWeek} keyboardType="number-pad" />

      <Text style={styles.sectionHeading}>Default Servings</Text>
      <TextInput style={styles.input} value={servings} onChangeText={setServings} keyboardType="number-pad" />

      <Text style={styles.sectionHeading}>Max Active Cooking Time (minutes)</Text>
      <TextInput style={styles.input} value={maxTime} onChangeText={setMaxTime} keyboardType="number-pad" placeholder="No limit" />

      <Text style={styles.sectionHeading}>Dietary Preferences</Text>
      <View style={styles.flags}>
        {DIETARY_FLAGS.map(flag => (
          <Pressable
            key={flag}
            style={[styles.flagBtn, dietaryFlags.includes(flag) && styles.flagBtnActive]}
            onPress={() => toggleFlag(flag)}
          >
            <Text style={dietaryFlags.includes(flag) ? styles.flagTextActive : styles.flagText}>{flag}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.saveBtn} onPress={save}>
        <Text style={styles.saveBtnText}>Save Settings</Text>
      </Pressable>

      <Text style={styles.sectionHeading}>Account</Text>
      <Pressable style={styles.dangerBtn} onPress={handleSignOut}>
        <Text style={styles.dangerBtnText}>Sign out</Text>
      </Pressable>

      {__DEV__ && (
        <>
          <Text style={styles.sectionHeading}>Developer</Text>
          <Pressable style={styles.devBtn} onPress={exportDb}>
            <Text style={styles.devBtnText}>Export SQLite DB</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  heading: { fontSize: 24, fontWeight: '700', marginBottom: 24 },
  sectionHeading: { fontSize: 14, fontWeight: '700', color: '#888', textTransform: 'uppercase', marginTop: 24, marginBottom: 8 },
  description: { fontSize: 13, color: '#666', marginBottom: 4 },
  input: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 10, fontSize: 15 },
  flags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  flagBtn: { borderWidth: 1, borderColor: '#ddd', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  flagBtnActive: { borderColor: '#2a9d8f', backgroundColor: '#2a9d8f' },
  flagText: { fontSize: 13, color: '#444' },
  flagTextActive: { fontSize: 13, color: '#fff' },
  saveBtn: { marginTop: 24, backgroundColor: '#2a9d8f', borderRadius: 8, padding: 14, alignItems: 'center' },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  dangerBtn: { borderWidth: 1, borderColor: '#e63946', borderRadius: 8, padding: 12, alignItems: 'center' },
  dangerBtnText: { color: '#e63946', fontWeight: '600' },
  devBtn: { borderWidth: 1, borderColor: '#f7a04a', borderRadius: 8, padding: 12, alignItems: 'center' },
  devBtnText: { color: '#f7a04a' },
});
```

- [ ] **Step 2: Install slider dependency**

```bash
cd mobile && npx expo install @react-native-community/slider
```

- [ ] **Step 3: Commit**

```bash
git add mobile/app/(tabs)/settings/index.tsx
git commit -m "⚙️ settings: full settings screen with all user config options"
```

---

### Task 4: Wire receipt scan cross-check into scan confirm flow

This task ensures that when a receipt is scanned and confirmed (from Plan 2), the `checkOffByIngredientIds` call uses the resolved ingredient IDs from the confirmed items. This is already implemented in `review.tsx` from Plan 2 — verify it is working end-to-end.

When the user scans a receipt via the "Completed checkout → Scan receipt" path (routing from shop via `returnTo=shop` query param), `review.tsx` should call `completeCheckout()` after confirming if the `returnTo=shop` param is present. This removes all checked shopping list items after the receipt scan updates pantry and cross-checks the shopping list.

- [ ] **Step 1: Verify review.tsx calls checkOffByIngredientIds**

```bash
grep -n "checkOffByIngredientIds" mobile/app/\(tabs\)/pantry/review.tsx
```
Expected: line with `await checkOffByIngredientIds(resolvedIds);`

If missing, add to the `confirm()` function in `review.tsx` (after the upsert loop):

```typescript
await checkOffByIngredientIds(resolvedIds);
```

- [ ] **Step 2: Handle `returnTo` param in review.tsx**

Add `useLocalSearchParams` to read the `returnTo` query param, import `completeCheckout` from `@/db/shopping`, and after `checkOffByIngredientIds` in the `confirm()` function:

```typescript
// In review.tsx confirm() function, after checkOffByIngredientIds:
const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
// ...
if (returnTo === 'shop') {
  await completeCheckout();
}
router.replace(returnTo === 'shop' ? '/(tabs)/shop' : '/(tabs)/pantry');
```

Import `completeCheckout` from `@/db/shopping` in `review.tsx`.

- [ ] **Step 3: Write integration test for the confirm flow**

```typescript
// mobile/src/__tests__/flows/receipt-confirm.test.ts
import { resolveOrCreateIngredient } from '@/db/ingredients';
import { upsertPantryItem } from '@/db/pantry';
import { checkOffByIngredientIds } from '@/db/shopping';

jest.mock('@/db/ingredients');
jest.mock('@/db/pantry');
jest.mock('@/db/shopping');

// Simulates what review.tsx confirm() does
async function simulateConfirm(items: Array<{ name: string; quantity: number; unit: string }>) {
  const resolvedIds: number[] = [];
  for (const item of items) {
    const id = await resolveOrCreateIngredient({ canonical_name: item.name });
    await upsertPantryItem({ ingredient_id: id, quantity: item.quantity, unit: item.unit });
    resolvedIds.push(id);
  }
  await checkOffByIngredientIds(resolvedIds);
}

describe('receipt confirm flow', () => {
  it('resolves ingredients, upserts pantry, and checks off shopping items', async () => {
    (resolveOrCreateIngredient as jest.Mock)
      .mockResolvedValueOnce(1)
      .mockResolvedValueOnce(2);
    (upsertPantryItem as jest.Mock).mockResolvedValue(undefined);
    (checkOffByIngredientIds as jest.Mock).mockResolvedValue(undefined);

    await simulateConfirm([
      { name: 'chicken breast', quantity: 500, unit: 'g' },
      { name: 'whole milk', quantity: 2000, unit: 'ml' },
    ]);

    expect(upsertPantryItem).toHaveBeenCalledTimes(2);
    expect(checkOffByIngredientIds).toHaveBeenCalledWith([1, 2]);
  });
});
```

- [ ] **Step 4: Run test**

```bash
cd mobile && npx jest src/__tests__/flows/receipt-confirm.test.ts --verbose
```
Expected: 1 passing

- [ ] **Step 5: Commit**

```bash
git add mobile/src/__tests__/flows/ mobile/app/\(tabs\)/pantry/review.tsx
git commit -m "✅ test: receipt confirm flow integration test + returnTo=shop handling"
```

---

### Task 5: Run full test suite

- [ ] **Step 1: Run all mobile tests**

```bash
cd mobile && npx jest --verbose
```
Expected: all tests passing, no failures

- [ ] **Step 2: Run all backend tests**

```bash
cd backend && uv run pytest -v
```
Expected: all tests passing

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "🎉 feat: Glean MVP — all 5 plans complete"
```
