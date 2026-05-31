// mobile/src/db/seed.ts
import type { SQLiteDatabase } from "expo-sqlite";
import { INGREDIENT_CATEGORIES } from "./ingredient-categories";

const STAPLES: Array<{ canonical_name: string; category: string; is_staple: 1 }> = [
  { canonical_name: "olive oil", category: "oils_fats", is_staple: 1 },
  { canonical_name: "salt", category: "spices", is_staple: 1 },
  { canonical_name: "black pepper", category: "spices", is_staple: 1 },
  { canonical_name: "garlic", category: "alliums", is_staple: 1 },
  { canonical_name: "onion", category: "alliums", is_staple: 1 },
  { canonical_name: "butter", category: "dairy", is_staple: 1 },
  { canonical_name: "eggs", category: "eggs", is_staple: 1 },
  { canonical_name: "plain flour", category: "grains", is_staple: 1 },
  { canonical_name: "sugar", category: "condiments", is_staple: 1 },
  { canonical_name: "tomato paste", category: "condiments", is_staple: 1 },
];

export async function seedDatabase(db: SQLiteDatabase): Promise<void> {
  const existing = await db.getFirstAsync<{ count: number }>(
    "SELECT COUNT(*) as count FROM ingredient_categories",
  );
  if (existing && existing.count > 0) return;

  await db.withTransactionAsync(async () => {
    for (const cat of INGREDIENT_CATEGORIES) {
      await db.runAsync("INSERT INTO ingredient_categories (category, food_group) VALUES (?, ?)", [
        cat.category,
        cat.food_group,
      ]);
    }
    for (const staple of STAPLES) {
      await db.runAsync(
        "INSERT INTO ingredients (canonical_name, category, is_staple) VALUES (?, ?, ?)",
        [staple.canonical_name, staple.category, staple.is_staple],
      );
    }
  });
}
