// Seed data ported from the Expo app's `src/db/ingredient-categories.ts`
// and `src/db/seed.ts` (see git history) — the 23-category taxonomy and the
// 10 staples (AC-DATA-10), plus the per-category shelf life the RN app
// never had (§6 Pantry: expiry is inferred automatically, so every
// category needs a default).
//
// Shelf-life values are reasonable defaults for a home fridge/pantry, not a
// clinically-verified table — inferred expiry is deliberately approximate
// (FLUTTER_MIGRATION.md ticket 23 defers user-correctable expiry).

/// One row of the ingredient-category taxonomy: the category key, its food
/// group (used for pantry grouping/filter chips and meal-plan balancing),
/// and its default shelf life in days from the day it's added to the
/// pantry.
class CategorySeed {
  const CategorySeed(this.category, this.foodGroup, this.shelfLifeDays);

  final String category;
  final String foodGroup;
  final int shelfLifeDays;
}

const List<CategorySeed> ingredientCategorySeeds = [
  CategorySeed('leafy_greens', 'vegetables', 5),
  CategorySeed('brassicas', 'vegetables', 10),
  CategorySeed('alliums', 'vegetables', 21),
  CategorySeed('root_vegetables', 'vegetables', 21),
  CategorySeed('nightshades', 'vegetables', 7),
  CategorySeed('legumes', 'protein', 180),
  CategorySeed('citrus', 'fruit', 14),
  CategorySeed('tropical_fruit', 'fruit', 7),
  CategorySeed('stone_fruit', 'fruit', 5),
  CategorySeed('berries', 'fruit', 4),
  CategorySeed('red_meat', 'protein', 3),
  CategorySeed('poultry', 'protein', 2),
  CategorySeed('seafood', 'protein', 2),
  CategorySeed('eggs', 'protein', 21),
  CategorySeed('dairy', 'dairy', 7),
  CategorySeed('grains', 'carbohydrates', 365),
  CategorySeed('pasta_rice', 'carbohydrates', 365),
  CategorySeed('bread', 'carbohydrates', 5),
  CategorySeed('oils_fats', 'fats', 180),
  CategorySeed('herbs_fresh', 'condiments', 5),
  CategorySeed('herbs_dried', 'condiments', 365),
  CategorySeed('spices', 'condiments', 365),
  CategorySeed('condiments', 'condiments', 180),
];

/// A staple ingredient seeded with `isStaple = true` so pantry logic that
/// treats staples specially (e.g. shopping shortfalls) has real data from
/// first launch.
class StapleSeed {
  const StapleSeed(this.canonicalName, this.category);

  final String canonicalName;
  final String category;
}

const List<StapleSeed> stapleSeeds = [
  StapleSeed('olive oil', 'oils_fats'),
  StapleSeed('salt', 'spices'),
  StapleSeed('black pepper', 'spices'),
  StapleSeed('garlic', 'alliums'),
  StapleSeed('onion', 'alliums'),
  StapleSeed('butter', 'dairy'),
  StapleSeed('eggs', 'eggs'),
  StapleSeed('plain flour', 'grains'),
  StapleSeed('sugar', 'condiments'),
  StapleSeed('tomato paste', 'condiments'),
];
