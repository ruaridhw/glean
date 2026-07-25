// Table definitions for the Glean drift database.
//
// Ported from `mobile/src/db/schema.ts` (Drizzle over expo-sqlite), with the
// schema changes required by FLUTTER_MIGRATION.md §3 and §6:
//
//   1. Every user-data table carries a `userId` column (AC-DATA-02). RN only
//      scoped `user_config`; `pantry_items`, `recipes`, `meal_plan_entries`
//      and `shopping_list_items` had none, so switching accounts on one
//      device inherited the previous user's groceries.
//   2. `ingredient_categories` gains `shelfLifeDays`, the basis for
//      automatic expiry inference (§6 Pantry) — nothing in the RN app ever
//      wrote an expiry date.
//   3. `meal_plan_entries.recipeId` is nullable with `onDelete: setNull`, and
//      the entry snapshots `recipeTitle` at creation time, so deleting a
//      recipe only drops the link rather than destroying the record of what
//      was cooked (AC-MEAL-03).
//   4. `shopping_list_items.ingredientId` is NOT NULL (AC-SHOP-03) and gains
//      `sourceMealPlanEntryId` so a deleted plan entry cascades its
//      plan-derived shopping rows away (AC-SHOP-06) without a manual sweep.
//   5. A new `cooked_adjustments` table records exactly what "Cooked" took
//      out of the pantry so it can be reversed (AC-UX-03).
//
// Dates/timestamps are stored as ISO-8601 TEXT throughout (matching the RN
// schema) rather than drift's `dateTime()` column, which defaults to unix
// timestamps and would need extra build config to match. ISO-8601 text also
// sorts and range-filters correctly with plain SQL comparisons, which the
// week-scoped plan queries rely on.
//
// Column and table SQL names are drift's default camelCase -> snake_case
// conversion; no `.named()` overrides are needed to match the original
// snake_case schema.
import 'package:drift/drift.dart';

/// The 23-category ingredient taxonomy (FLUTTER_MIGRATION.md §9), each with
/// the shelf-life-in-days used to infer pantry expiry automatically.
class IngredientCategories extends Table {
  TextColumn get category => text()();
  TextColumn get foodGroup => text()();
  IntColumn get shelfLifeDays => integer()();

  @override
  Set<Column> get primaryKey => {category};
}

/// A resolved ingredient identity, shared across pantry, recipes and
/// shopping. Not user-scoped: it is a catalog of ingredient names, not user
/// data.
///
/// `category` stays nullable at the schema level because recipe-import
/// ingredients still have no source of category (recipe endpoints are
/// outside the §9 backend change) — but every pantry/shopping intake path in
/// this data layer requires a non-null, taxonomy-valid category when
/// resolving an ingredient, which is what actually makes `food_group`
/// non-nullable where it matters (AC-DATA-11): pantry item reads. See
/// `IngredientsRepository.resolveOrCreate`.
class Ingredients extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get canonicalName => text().unique()();
  TextColumn get apiIngredientId => text().nullable()();
  TextColumn get apiName => text().nullable()();
  TextColumn get category =>
      text().nullable().references(IngredientCategories, #category)();
  TextColumn get canonicalUnit => text().nullable()();
  BoolColumn get isStaple => boolean().withDefault(const Constant(false))();
}

class PantryItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get ingredientId => integer().references(Ingredients, #id)();
  RealColumn get quantity => real()();
  TextColumn get unit => text()();
  RealColumn get unitPrice => real().nullable()();
  TextColumn get expiryDate => text().nullable()();
  TextColumn get lastUsedAt => text().nullable()();
  TextColumn get updatedAt => text()();

  // `upsertItem` depends on at most one row per (user, ingredient); the RN
  // schema never enforced this at the DB level.
  @override
  List<Set<Column>> get uniqueKeys => [
    {userId, ingredientId},
  ];
}

/// A user's saved/imported recipe library (not the read-only server-side
/// search corpus — that never lands here until the user saves it).
class Recipes extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  TextColumn get externalId => text().nullable()();
  TextColumn get title => text()();
  TextColumn get sourceUrl => text().nullable()();
  TextColumn get cuisine => text().nullable()();
  TextColumn get difficulty => text().nullable()();
  IntColumn get activeTimeMins => integer().nullable()();
  IntColumn get totalTimeMins => integer().nullable()();
  TextColumn get notSuitableFor => text().withDefault(const Constant('[]'))();
  IntColumn get yieldCount => integer().nullable()();
  TextColumn get nutrition => text().nullable()();
  TextColumn get instructions => text().withDefault(const Constant('[]'))();
  TextColumn get lastCookedAt => text().nullable()();

  // "already saved" dedupe (AC-MEAL-10) is per user, not global.
  @override
  List<Set<Column>> get uniqueKeys => [
    {userId, externalId},
  ];
}

class RecipeDietaryFlags extends Table {
  IntColumn get recipeId =>
      integer().references(Recipes, #id, onDelete: KeyAction.cascade)();
  TextColumn get flag => text()();

  @override
  Set<Column> get primaryKey => {recipeId, flag};
}

class RecipeIngredients extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get recipeId =>
      integer().references(Recipes, #id, onDelete: KeyAction.cascade)();
  IntColumn get ingredientId => integer().references(Ingredients, #id)();
  RealColumn get quantity => real()();
  TextColumn get unit => text()();
  TextColumn get preparation => text().nullable()();
  BoolColumn get isOptional => boolean().withDefault(const Constant(false))();
  TextColumn get substitutions => text().withDefault(const Constant('[]'))();
}

/// A planned meal. `recipeId` is nullable with `onDelete: setNull` and
/// `recipeTitle` is captured at creation time so deleting the recipe from the
/// library keeps this entry showing what was (or is being) cooked
/// (AC-MEAL-03) instead of losing the row or dangling on a missing FK.
class MealPlanEntries extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get recipeId => integer().nullable().references(
    Recipes,
    #id,
    onDelete: KeyAction.setNull,
  )();
  TextColumn get recipeTitle => text()();
  // ISO date (YYYY-MM-DD), the day within the entry's plan week. Now
  // load-bearing: week-scoped queries and rollover both filter/write it
  // (AC-PLAN-01).
  TextColumn get plannedDate => text()();
  TextColumn get cookedAt => text().nullable()();
  // No default: every call site must state servings explicitly so
  // `preferred_servings` can never be silently re-hardcoded to 1
  // (AC-PLAN-07) the way RN's `addMealPlanEntry` did.
  IntColumn get servings => integer()();
}

/// The exact pantry delta "Cooked" applied for one plan entry, so it can be
/// reversed precisely (AC-UX-03) rather than approximated. One row per
/// ingredient the recipe touched.
class CookedAdjustments extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get mealPlanEntryId =>
      integer().references(MealPlanEntries, #id, onDelete: KeyAction.cascade)();
  IntColumn get ingredientId => integer().references(Ingredients, #id)();
  // The amount actually subtracted from the pantry row, in that row's unit —
  // not the recipe's raw requirement. If the pantry only had 2 units of an
  // ingredient a recipe needed 3 of, the floor-at-zero decrement only
  // removes 2; recording the requirement instead of the applied delta would
  // over-restore on undo.
  RealColumn get amountDeducted => real()();
  TextColumn get unit => text()();
  // Snapshot of the pantry row's `lastUsedAt` immediately before this cook,
  // so undo restores that too, not just the quantity.
  TextColumn get previousLastUsedAt => text().nullable()();
  TextColumn get createdAt => text()();
}

/// `ingredientId` is NOT NULL (AC-SHOP-03) — manual entries resolve an
/// ingredient identity through `IngredientsRepository` rather than storing a
/// bare name, which is what let them dodge every receipt match in RN.
///
/// `sourceMealPlanEntryId` links a plan-derived row back to the entry that
/// created it, so deleting the entry cascades away just its own gap rows
/// (AC-SHOP-06) instead of requiring a manual sweep.
class ShoppingListItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get ingredientId => integer().references(Ingredients, #id)();
  TextColumn get name => text()();
  RealColumn get quantity => real().nullable()();
  TextColumn get unit => text().nullable()();
  TextColumn get source => text().withDefault(const Constant('manual'))();
  BoolColumn get isChecked => boolean().withDefault(const Constant(false))();
  IntColumn get sourceMealPlanEntryId => integer().nullable().references(
    MealPlanEntries,
    #id,
    onDelete: KeyAction.cascade,
  )();
}

class UserConfig extends Table {
  // The Cognito user sub (UUID) — this table's PK doubles as "the current
  // user id" for every other table's `userId` column.
  TextColumn get id => text()();
  RealColumn get purchaseTolerance => real().withDefault(const Constant(0.5))();
  IntColumn get preferredServings => integer().withDefault(const Constant(2))();
  IntColumn get mealsPerWeek => integer().withDefault(const Constant(5))();
  TextColumn get dietaryFlags => text().withDefault(const Constant('[]'))();
  IntColumn get maxActiveTimeMins => integer().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}
