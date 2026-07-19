// mobile/src/db/pantry.ts

import { eq, sql } from "drizzle-orm";
import { normalizeUnit } from "@/normalization/units";
import type { PantryItem } from "@/types";
import { drizzleDb } from "./client";
import { resolveOrCreateIngredient } from "./ingredients";
import { ingredientCategories, ingredients, pantryItems } from "./schema";

export async function getPantryItems(): Promise<PantryItem[]> {
  const rows = await drizzleDb
    .select({
      id: pantryItems.id,
      ingredient_id: pantryItems.ingredient_id,
      quantity: pantryItems.quantity,
      unit: pantryItems.unit,
      unit_price: pantryItems.unit_price,
      expiry_date: pantryItems.expiry_date,
      last_used_at: pantryItems.last_used_at,
      updated_at: pantryItems.updated_at,
      canonical_name: ingredients.canonical_name,
      is_staple: ingredients.is_staple,
      food_group: ingredientCategories.food_group,
    })
    .from(pantryItems)
    .innerJoin(ingredients, eq(pantryItems.ingredient_id, ingredients.id))
    .leftJoin(ingredientCategories, eq(ingredients.category, ingredientCategories.category))
    .orderBy(
      sql`CASE WHEN ${pantryItems.expiry_date} IS NOT NULL THEN ${pantryItems.expiry_date} ELSE '9999-12-31' END`,
      sql`CASE WHEN ${pantryItems.last_used_at} IS NOT NULL THEN ${pantryItems.last_used_at} ELSE '0000-01-01' END`,
    );
  return rows as PantryItem[];
}

export async function upsertPantryItem(params: {
  ingredient_id: number;
  quantity: number;
  unit: string;
  unit_price?: number | null;
  expiry_date?: string | null;
}): Promise<void> {
  const existing = await drizzleDb
    .select({ id: pantryItems.id })
    .from(pantryItems)
    .where(eq(pantryItems.ingredient_id, params.ingredient_id))
    .limit(1);

  const match = existing[0];
  if (match) {
    await drizzleDb
      .update(pantryItems)
      .set({
        quantity: sql`${pantryItems.quantity} + ${params.quantity}`,
        unit_price: sql`COALESCE(${params.unit_price ?? null}, ${pantryItems.unit_price})`,
        updated_at: sql`datetime('now')`,
      })
      .where(eq(pantryItems.id, match.id));
  } else {
    await drizzleDb.insert(pantryItems).values({
      ingredient_id: params.ingredient_id,
      quantity: params.quantity,
      unit: params.unit,
      unit_price: params.unit_price ?? null,
      expiry_date: params.expiry_date ?? null,
    });
  }
}

/**
 * Resolves (or creates) the ingredient for `name`, normalizes the quantity/unit
 * against the ingredient's canonical unit, and upserts the pantry row. This is
 * the single entry point for adding an item to the pantry — callers should not
 * assemble resolve → normalize → upsert themselves.
 */
export async function addPantryItem(params: {
  name: string;
  quantity: number;
  unit: string;
  unit_price?: number | null;
}): Promise<{ ingredientId: number }> {
  const ingredient = await resolveOrCreateIngredient({ canonical_name: params.name });
  const normalized = normalizeUnit({
    quantity: params.quantity,
    unit: params.unit,
    canonicalUnit: ingredient.canonical_unit ?? null,
    canonicalName: ingredient.canonical_name,
  });
  await upsertPantryItem({
    ingredient_id: ingredient.id,
    quantity: normalized?.quantity ?? params.quantity,
    unit: normalized?.unit ?? params.unit,
    unit_price: params.unit_price ?? null,
  });
  return { ingredientId: ingredient.id };
}

export async function updatePantryQuantity(id: number, quantity: number): Promise<void> {
  await drizzleDb
    .update(pantryItems)
    .set({ quantity, updated_at: sql`datetime('now')` })
    .where(eq(pantryItems.id, id));
}

export async function deletePantryItem(id: number): Promise<void> {
  await drizzleDb.delete(pantryItems).where(eq(pantryItems.id, id));
}
