// Table definitions for the Glean drift database.
//
// - Every user-data table carries a `userId` column, so switching accounts on one device never exposes
//   another user's data.
// - `ingredient_categories.shelfLifeDays` is the basis for automatic expiry inference.
// - `meal_plan_entries.recipeId` is nullable with `onDelete: setNull`, and the entry snapshots `recipeTitle`,
//   so deleting a recipe only drops the link.
// - `shopping_list_items.ingredientId` is NOT NULL, and `sourceMealPlanEntryId` cascades a deleted plan
//   entry's shopping rows away.
// - `cooked_adjustments` records exactly what "Cooked" took from the pantry so it can be reversed.
//
// Dates/timestamps are ISO-8601 TEXT rather than drift's `dateTime()`; text sorts and range-filters correctly
// with plain SQL comparisons, which the week-scoped plan queries rely on. SQL names are drift's default
// camelCase to snake_case.
import 'package:drift/drift.dart';

/// The 23-category ingredient taxonomy, each with the shelf life in days used to infer pantry expiry.
class IngredientCategories extends Table {
  TextColumn get category => text()();
  TextColumn get foodGroup => text()();
  IntColumn get shelfLifeDays => integer()();

  @override
  Set<Column> get primaryKey => {category};
}

/// A resolved ingredient identity shared across pantry, recipes and shopping. Not user-scoped: it is a
/// catalog of names.
///
/// `category` is nullable because recipe-import ingredients have no category source, but every pantry/shopping
/// intake path requires a non-null, taxonomy-valid one, which makes `food_group` non-nullable on pantry reads.
/// See `IngredientsRepository.resolveOrCreate`.
class Ingredients extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get canonicalName => text().unique()();
  TextColumn get apiIngredientId => text().nullable()();
  TextColumn get apiName => text().nullable()();
  TextColumn get category =>
      text().nullable().references(IngredientCategories, #category)();
  TextColumn get canonicalUnit => text().nullable()();
  BoolColumn get isStaple => boolean().withDefault(const Constant(false))();
  // The household's own choice of store section for this ingredient (a `StoreSection.dbValue`), or null to
  // use the section derived from its name and category.
  TextColumn get storeSection => text().nullable()();
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

  // `upsertItem` depends on at most one row per (user, ingredient).
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

  // "Already saved" dedupe is per user, not global.
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

/// A planned meal. `recipeId` is nullable with `onDelete: setNull` and `recipeTitle` is captured at creation,
/// so deleting the recipe keeps the entry.
class MealPlanEntries extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get recipeId => integer().nullable().references(
    Recipes,
    #id,
    onDelete: KeyAction.setNull,
  )();
  TextColumn get recipeTitle => text()();
  // ISO date (YYYY-MM-DD), the day within the entry's plan week; week-scoped queries and rollover use it.
  TextColumn get plannedDate => text()();
  TextColumn get cookedAt => text().nullable()();
  // Survives library deletion so corpus exclusion keeps its identity.
  TextColumn get externalIdSnapshot => text().nullable()();
  // Undo restores/forwards this history snapshot, just like pantry deltas.
  TextColumn get previousRecipeCookedAt => text().nullable()();
  // No default: every call site must state servings so `preferred_servings` can't be silently hardcoded to 1.
  IntColumn get servings => integer()();
}

/// The exact pantry delta "Cooked" applied for one plan entry, so it can be reversed precisely. One row per
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

/// `ingredientId` is NOT NULL: manual entries resolve an ingredient identity through `IngredientsRepository`
/// so they can match a receipt.
///
/// `sourceMealPlanEntryId` links a plan-derived row to its entry, so deleting the entry cascades away just its
/// own gap rows.
class ShoppingListItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get ingredientId => integer().references(Ingredients, #id)();
  TextColumn get name => text()();
  RealColumn get quantity => real().nullable()();
  TextColumn get unit => text().nullable()();
  TextColumn get source => text().withDefault(const Constant('manual'))();
  // New plan rows store full demand. Display allocates stock once across
  // them; legacy v1 gaps retain their already-computed shortfall semantics.
  BoolColumn get isRequirement =>
      boolean().withDefault(const Constant(false))();
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
  // Backs first-run onboarding completion. Defaults false so a user with no row yet reads as not onboarded.
  BoolColumn get onboardingCompleted =>
      boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}
