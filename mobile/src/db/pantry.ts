// mobile/src/db/pantry.ts

import type { PantryItem } from "@/types";
import { getDb } from "./client";

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
    "SELECT id, quantity FROM pantry_items WHERE ingredient_id = ?",
    [params.ingredient_id],
  );

  if (existing) {
    await db.runAsync(
      `UPDATE pantry_items
       SET quantity = quantity + ?, unit_price = COALESCE(?, unit_price), updated_at = datetime('now')
       WHERE id = ?`,
      [params.quantity, params.unit_price ?? null, existing.id],
    );
  } else {
    await db.runAsync(
      `INSERT INTO pantry_items (ingredient_id, quantity, unit, unit_price, expiry_date)
       VALUES (?, ?, ?, ?, ?)`,
      [
        params.ingredient_id,
        params.quantity,
        params.unit,
        params.unit_price ?? null,
        params.expiry_date ?? null,
      ],
    );
  }
}

export async function updatePantryQuantity(id: number, quantity: number): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    `UPDATE pantry_items SET quantity = ?, updated_at = datetime('now') WHERE id = ?`,
    [quantity, id],
  );
}

export async function deletePantryItem(id: number): Promise<void> {
  const db = await getDb();
  await db.runAsync("DELETE FROM pantry_items WHERE id = ?", [id]);
}
