// mobile/src/db/shopping.ts

import { and, eq, inArray, sql } from "drizzle-orm";
import type { ShoppingListItem } from "@/types";
import { drizzleDb } from "./client";
import { resolveOrCreateIngredient } from "./ingredients";
import { ingredients, pantryItems, recipeIngredients, shoppingListItems } from "./schema";

export async function getShoppingListItems(): Promise<ShoppingListItem[]> {
  const rows = await drizzleDb
    .select({
      id: shoppingListItems.id,
      ingredient_id: shoppingListItems.ingredient_id,
      name: sql<string>`COALESCE(${ingredients.canonical_name}, ${shoppingListItems.name})`,
      quantity: shoppingListItems.quantity,
      unit: shoppingListItems.unit,
      source: shoppingListItems.source,
      is_checked: shoppingListItems.is_checked,
    })
    .from(shoppingListItems)
    .leftJoin(ingredients, eq(shoppingListItems.ingredient_id, ingredients.id))
    .orderBy(sql`${shoppingListItems.is_checked} ASC, ${shoppingListItems.id} DESC`);
  return rows as ShoppingListItem[];
}

// When a recipe is added to the plan, compute which ingredients are
// insufficient in the pantry and add them to the shopping list.
export async function addShoppingGapsForRecipe(
  recipeId: number,
  servings: number = 1,
): Promise<void> {
  const recipeIngs = await drizzleDb
    .select({
      ingredient_id: recipeIngredients.ingredient_id,
      canonical_name: ingredients.canonical_name,
      quantity: recipeIngredients.quantity,
      unit: recipeIngredients.unit,
    })
    .from(recipeIngredients)
    .innerJoin(ingredients, eq(recipeIngredients.ingredient_id, ingredients.id))
    .where(
      and(eq(recipeIngredients.recipe_id, recipeId), eq(recipeIngredients.is_optional, false)),
    );

  for (const ing of recipeIngs) {
    const needed = ing.quantity * servings;

    const [pantryRow] = await drizzleDb
      .select({ quantity: pantryItems.quantity })
      .from(pantryItems)
      .where(eq(pantryItems.ingredient_id, ing.ingredient_id));

    const available = pantryRow?.quantity ?? 0;
    if (available >= needed) continue;

    const shortfall = needed - available;

    // Don't duplicate — check if already on list
    const [existing] = await drizzleDb
      .select({ id: shoppingListItems.id })
      .from(shoppingListItems)
      .where(
        and(
          eq(shoppingListItems.ingredient_id, ing.ingredient_id),
          eq(shoppingListItems.is_checked, false),
        ),
      );

    if (!existing) {
      await drizzleDb.insert(shoppingListItems).values({
        ingredient_id: ing.ingredient_id,
        name: ing.canonical_name,
        quantity: shortfall,
        unit: ing.unit,
        source: "meal_plan",
      });
    }
  }
}

export async function checkOffByIngredientIds(ingredientIds: number[]): Promise<void> {
  if (ingredientIds.length === 0) return;
  await drizzleDb
    .update(shoppingListItems)
    .set({ is_checked: true })
    .where(inArray(shoppingListItems.ingredient_id, ingredientIds));
}

export async function addManualShoppingItem(params: {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  ingredient_id?: number | null;
}): Promise<void> {
  await drizzleDb.insert(shoppingListItems).values({
    ingredient_id: params.ingredient_id ?? null,
    name: params.name,
    quantity: params.quantity ?? null,
    unit: params.unit ?? null,
    source: "manual",
  });
}

export async function addAiShoppingItems(
  items: readonly {
    name: string;
    quantity: number;
    unit: string;
    api_ingredient_id?: string | null;
    category?: string | null;
  }[],
): Promise<void> {
  if (items.length === 0) return;

  const rows: {
    ingredient_id: number;
    name: string;
    quantity: number;
    unit: string;
    source: "ai";
  }[] = [];

  for (const item of items) {
    const ingredientId = await resolveOrCreateIngredient({
      canonical_name: item.name,
      api_ingredient_id: item.api_ingredient_id ?? null,
      category: item.category ?? null,
    });
    rows.push({
      ingredient_id: ingredientId,
      name: item.name,
      quantity: item.quantity,
      unit: item.unit,
      source: "ai",
    });
  }

  await drizzleDb.insert(shoppingListItems).values(rows);
}

export async function toggleShoppingItem(id: number, checked: boolean): Promise<void> {
  await drizzleDb
    .update(shoppingListItems)
    .set({ is_checked: checked })
    .where(eq(shoppingListItems.id, id));
}

export async function deleteShoppingItem(id: number): Promise<void> {
  await drizzleDb.delete(shoppingListItems).where(eq(shoppingListItems.id, id));
}

export async function completeCheckout(): Promise<void> {
  await drizzleDb.delete(shoppingListItems).where(eq(shoppingListItems.is_checked, true));
}
