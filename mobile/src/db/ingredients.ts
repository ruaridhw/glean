// mobile/src/db/ingredients.ts

import type { Ingredient } from "@/types";
import { getDb } from "./client";

// Find by canonical name (exact match). Returns null if not found.
export async function findIngredientByName(canonicalName: string): Promise<Ingredient | null> {
  const db = await getDb();
  return db.getFirstAsync<Ingredient>("SELECT * FROM ingredients WHERE canonical_name = ?", [
    canonicalName.toLowerCase().trim(),
  ]);
}

// Find by api_ingredient_id UUID.
export async function findIngredientByApiId(apiId: string): Promise<Ingredient | null> {
  const db = await getDb();
  return db.getFirstAsync<Ingredient>("SELECT * FROM ingredients WHERE api_ingredient_id = ?", [
    apiId,
  ]);
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
    [name, params.api_ingredient_id ?? null, params.api_name ?? null, params.category ?? null],
  );
  return result.lastInsertRowId;
}
