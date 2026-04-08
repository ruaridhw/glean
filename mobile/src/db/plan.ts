// mobile/src/db/plan.ts
import { count, eq, sql } from "drizzle-orm";
import { normalizeUnit } from "@/normalization/units";
import type { MealPlanEntry } from "@/types";
import { drizzleDb } from "./client";
import { ingredients, mealPlanEntries, pantryItems, recipeIngredients, recipes } from "./schema";

export async function getMealPlanEntries(): Promise<MealPlanEntry[]> {
  return drizzleDb
    .select({
      id: mealPlanEntries.id,
      recipe_id: mealPlanEntries.recipe_id,
      planned_date: mealPlanEntries.planned_date,
      cooked_at: mealPlanEntries.cooked_at,
      servings: mealPlanEntries.servings,
      recipe_title: recipes.title,
    })
    .from(mealPlanEntries)
    .innerJoin(recipes, eq(mealPlanEntries.recipe_id, recipes.id))
    .orderBy(mealPlanEntries.id);
}

export async function getMealPlanCount(): Promise<number> {
  const [row] = await drizzleDb.select({ count: count() }).from(mealPlanEntries);
  return row?.count ?? 0;
}

export async function addMealPlanEntry(recipeId: number, servings: number = 1): Promise<number> {
  const result = await drizzleDb
    .insert(mealPlanEntries)
    .values({ recipe_id: recipeId, planned_date: sql`(date('now'))`, servings })
    .returning({ id: mealPlanEntries.id });
  if (!result[0]) throw new Error("Insert did not return an id");
  return result[0].id;
}

export async function deleteMealPlanEntry(id: number): Promise<void> {
  await drizzleDb.delete(mealPlanEntries).where(eq(mealPlanEntries.id, id));
}

// Marks a meal as cooked:
// 1. Sets cooked_at on the entry
// 2. Decrements pantry quantities (floor at 0) with unit normalization
// 3. Stamps last_used_at on affected pantry rows
// 4. Stamps last_cooked_at on the recipe
export async function markMealAsCooked(entryId: number): Promise<void> {
  const [entry] = await drizzleDb
    .select({ recipe_id: mealPlanEntries.recipe_id, servings: mealPlanEntries.servings })
    .from(mealPlanEntries)
    .where(eq(mealPlanEntries.id, entryId));

  if (!entry) throw new Error(`Meal plan entry ${entryId} not found`);

  const recipeIngs = await drizzleDb
    .select({
      ingredient_id: recipeIngredients.ingredient_id,
      quantity: recipeIngredients.quantity,
      unit: recipeIngredients.unit,
    })
    .from(recipeIngredients)
    .where(eq(recipeIngredients.recipe_id, entry.recipe_id));

  const now = new Date().toISOString();

  for (const ing of recipeIngs) {
    const [ingredientRow] = await drizzleDb
      .select({
        canonical_unit: ingredients.canonical_unit,
        canonical_name: ingredients.canonical_name,
      })
      .from(ingredients)
      .where(eq(ingredients.id, ing.ingredient_id));

    const [pantryRow] = await drizzleDb
      .select({ unit: pantryItems.unit })
      .from(pantryItems)
      .where(eq(pantryItems.ingredient_id, ing.ingredient_id));

    let decrementQuantity = ing.quantity * entry.servings;
    if (pantryRow && ingredientRow) {
      const normalized = normalizeUnit({
        quantity: ing.quantity * entry.servings,
        unit: ing.unit,
        canonicalUnit: pantryRow.unit,
        canonicalName: ingredientRow.canonical_name,
      });
      if (normalized) decrementQuantity = normalized.quantity;
    }

    await drizzleDb
      .update(pantryItems)
      .set({
        quantity: sql`MAX(0, ${pantryItems.quantity} - ${decrementQuantity})`,
        last_used_at: now,
        updated_at: sql`(datetime('now'))`,
      })
      .where(eq(pantryItems.ingredient_id, ing.ingredient_id));
  }

  await drizzleDb
    .update(recipes)
    .set({ last_cooked_at: now })
    .where(eq(recipes.id, entry.recipe_id));

  await drizzleDb
    .update(mealPlanEntries)
    .set({ cooked_at: now })
    .where(eq(mealPlanEntries.id, entryId));
}
