export const INGREDIENT_CATEGORIES = [
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
] as const;

const CATEGORY_NAMES: ReadonlySet<string> = new Set(
  INGREDIENT_CATEGORIES.map((item) => item.category),
);

export function normaliseIngredientCategory(category: string | null | undefined): string | null {
  if (!category) return null;
  const normalized = category.trim().toLowerCase();
  return CATEGORY_NAMES.has(normalized) ? normalized : null;
}
