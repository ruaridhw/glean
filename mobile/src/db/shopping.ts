// mobile/src/db/shopping.ts
import { getDb } from "./client";

// Mark shopping list items as checked if they match any of the given ingredient_ids.
export async function checkOffByIngredientIds(ingredientIds: number[]): Promise<void> {
  if (ingredientIds.length === 0) return;
  const db = await getDb();
  const placeholders = ingredientIds.map(() => "?").join(", ");
  await db.runAsync(
    `UPDATE shopping_list_items SET is_checked = 1 WHERE ingredient_id IN (${placeholders})`,
    ingredientIds,
  );
}
