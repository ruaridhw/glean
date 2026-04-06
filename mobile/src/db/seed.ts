// mobile/src/db/seed.ts
import type { SQLiteDatabase } from "expo-sqlite";

const CATEGORIES: Array<{ category: string; food_group: string }> = [
  { category: "leafy_greens", food_group: "vegetables" },
  { category: "brassicas", food_group: "vegetables" },
  { category: "alliums", food_group: "vegetables" },
  { category: "root_vegetables", food_group: "vegetables" },
  { category: "nightshades", food_group: "vegetables" },
  { category: "legumes", food_group: "protein" },
  { category: "citrus", food_group: "fruit" },
  { category: "tropical_fruit", food_group: "fruit" },
  { category: "stone_fruit", food_group: "fruit" },
  { category: "berries", food_group: "fruit" },
  { category: "red_meat", food_group: "protein" },
  { category: "poultry", food_group: "protein" },
  { category: "seafood", food_group: "protein" },
  { category: "eggs", food_group: "protein" },
  { category: "dairy", food_group: "dairy" },
  { category: "grains", food_group: "carbohydrates" },
  { category: "pasta_rice", food_group: "carbohydrates" },
  { category: "bread", food_group: "carbohydrates" },
  { category: "oils_fats", food_group: "fats" },
  { category: "herbs_fresh", food_group: "condiments" },
  { category: "herbs_dried", food_group: "condiments" },
  { category: "spices", food_group: "condiments" },
  { category: "condiments", food_group: "condiments" },
];

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
    for (const cat of CATEGORIES) {
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
