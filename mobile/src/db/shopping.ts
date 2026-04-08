// mobile/src/db/shopping.ts

import { inArray } from "drizzle-orm";
import { drizzleDb } from "./client";
import { shoppingListItems } from "./schema";

export async function checkOffByIngredientIds(ingredientIds: number[]): Promise<void> {
  if (ingredientIds.length === 0) return;
  await drizzleDb
    .update(shoppingListItems)
    .set({ is_checked: true })
    .where(inArray(shoppingListItems.ingredient_id, ingredientIds));
}
