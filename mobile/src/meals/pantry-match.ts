// mobile/src/meals/pantry-match.ts
//
// "n of m in pantry" recipe match indicator.
//
// Recipe ingredients (`recipe_ingredients`) and pantry items (`pantry_items`)
// both reference the shared `ingredients` table. Ingredient rows are deduped at
// write time by `api_ingredient_id` then normalized `canonical_name`
// (see resolveOrCreateIngredient), so matching purely by `ingredient_id`
// already collapses the "same ingredient by normalized name" case — no extra
// name comparison is needed here.

import { gt, inArray } from "drizzle-orm";
import { drizzleDb } from "@/db/client";
import { pantryItems, recipeIngredients } from "@/db/schema";

export interface PantryMatch {
  /** Recipe ingredients the pantry currently covers. */
  n: number;
  /** Total ingredients in the recipe. */
  m: number;
}

/**
 * Pure matcher: an ingredient counts as "in pantry" when its ingredient_id is
 * present in the pantry set. Kept side-effect free so it can be unit tested
 * without a database.
 */
export function computePantryMatch(
  recipeIngredientIds: number[],
  pantryIngredientIds: ReadonlySet<number>,
): PantryMatch {
  const m = recipeIngredientIds.length;
  const n = recipeIngredientIds.reduce(
    (count, id) => (pantryIngredientIds.has(id) ? count + 1 : count),
    0,
  );
  return { n, m };
}

export function formatPantryMatch(match: PantryMatch): string {
  return `${match.n} of ${match.m} in pantry`;
}

/** ingredient_ids the user currently holds in the pantry (quantity > 0). */
export async function getPantryIngredientIds(): Promise<Set<number>> {
  const rows = await drizzleDb
    .select({ ingredient_id: pantryItems.ingredient_id })
    .from(pantryItems)
    .where(gt(pantryItems.quantity, 0));
  return new Set(rows.map((row) => row.ingredient_id));
}

/**
 * Pantry match ({n, m}) for each recipe id — one pantry read plus one
 * recipe-ingredient read, regardless of how many recipes are passed.
 */
export async function getPantryMatchesForRecipes(
  recipeIds: number[],
): Promise<Map<number, PantryMatch>> {
  const result = new Map<number, PantryMatch>();
  if (recipeIds.length === 0) return result;

  const [pantryIngredientIds, ingredientRows] = await Promise.all([
    getPantryIngredientIds(),
    drizzleDb
      .select({
        recipe_id: recipeIngredients.recipe_id,
        ingredient_id: recipeIngredients.ingredient_id,
      })
      .from(recipeIngredients)
      .where(inArray(recipeIngredients.recipe_id, recipeIds)),
  ]);

  const byRecipe = new Map<number, number[]>();
  for (const row of ingredientRows) {
    const list = byRecipe.get(row.recipe_id);
    if (list) list.push(row.ingredient_id);
    else byRecipe.set(row.recipe_id, [row.ingredient_id]);
  }

  for (const id of recipeIds) {
    result.set(id, computePantryMatch(byRecipe.get(id) ?? [], pantryIngredientIds));
  }
  return result;
}
