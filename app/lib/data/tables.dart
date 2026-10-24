// Table definitions for the Glean drift database.
//
// - Every user-data table carries a `userId` column, so switching accounts on one device never exposes
//   another user's data.
// - `ingredients.groupId` is the ingredient group; `catalogueItemId` links an ingredient to a synced catalogue item
//   once its name matches one, and `form` stays null until someone states it (it is never defaulted).
// - `meal_plan_entries.recipeId` is nullable with `onDelete: setNull`, and the entry snapshots `recipeTitle`,
//   so deleting a recipe only drops the link.
// - `shopping_list_items.ingredientId` is NOT NULL, and `sourceMealPlanEntryId` cascades a deleted plan
//   entry's shopping rows away.
// - `cooked_adjustments` records exactly what "Cooked" took from the pantry so it can be reversed.
// - `meal_ratings` holds the household's thumb (and optional note) on a cooked entry, one row per entry.
//
// Dates/timestamps are ISO-8601 TEXT rather than drift's `dateTime()`; text sorts and range-filters correctly
// with plain SQL comparisons, which the week-scoped plan queries rely on. SQL names are drift's default
// camelCase to snake_case.
import 'package:drift/drift.dart';

/// A resolved ingredient identity shared across pantry, recipes and shopping. Not user-scoped: it is a
/// catalog of names.
///
/// `groupId` is nullable because recipe-import ingredients have no group source; a pantry read then shows food group
/// "other". `catalogueItemId` is deliberately not a foreign key: the catalogue may be empty or behind, and an
/// ingredient must work without an item. See `IngredientsRepository.resolveOrCreate`.
class Ingredients extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get canonicalName => text().unique()();
  TextColumn get apiName => text().nullable()();
  TextColumn get groupId =>
      text().nullable().references(IngredientGroups, #id)();
  TextColumn get catalogueItemId => text().nullable()();
  TextColumn get form => text().nullable()();
  TextColumn get canonicalUnit => text().nullable()();
  BoolColumn get isStaple => boolean().withDefault(const Constant(false))();
  // The household's own choice of store section for this ingredient (a `StoreSection.dbValue`), or null to
  // use the section derived from its name and group. Only held here while the ingredient has no catalogue item:
  // linking moves it into `ingredient_overrides`.
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

/// The household's verdict on a meal they cooked: a thumb, and optionally why. One row per plan entry, so
/// switching the thumb updates it and clearing the thumb deletes it — a meal is never rated twice.
///
/// Only cooked entries are rated (the repository refuses an uncooked one): an uncooked meal says nothing
/// reliable about taste. Rows cascade away with their entry, and travel to the planner inside the cooked
/// history window, where a thumbs down keeps the recipe out of future plans.
class MealRatings extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  IntColumn get mealPlanEntryId => integer()
      .references(MealPlanEntries, #id, onDelete: KeyAction.cascade)
      .unique()();
  // `MealThumb.dbValue` ('up' or 'down'). Never null: clearing the rating deletes the row.
  TextColumn get rating => text()();
  // Free text the household typed in the long-press sheet; null when they saved no comment.
  TextColumn get note => text().nullable()();
  TextColumn get createdAt => text()();
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
  // Whether the Shopping tab groups rows by store section. Lives on this device's database, so it is a
  // per-device choice; defaults off.
  BoolColumn get groupShoppingBySection =>
      boolean().withDefault(const Constant(false))();
  // Whether the one-off "how ratings are used" explainer has been shown. Defaults false, so a user with no
  // row yet gets it on their first thumb; the flag lives here rather than in a table of its own.
  BoolColumn get ratingsExplainerSeen =>
      boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

/// An ingredient group and the default rules its catalogue items take: seeded in the app, then kept in step with
/// the backend by catalogue sync. The per-form shelf lives are JSON objects keyed by form, because which forms a
/// group allows differs by group.
class IngredientGroups extends Table {
  TextColumn get id => text()();
  TextColumn get name => text()();
  TextColumn get kind => text()();
  TextColumn get foodGroup => text()();
  TextColumn get trackingMode => text()();
  TextColumn get stockUnit => text().nullable()();
  TextColumn get allowedForms => text()();
  TextColumn get unopenedShelfLifeDays => text()();
  TextColumn get onceOpenedShelfLifeDays => text()();

  @override
  Set<Column> get primaryKey => {id};
}

/// A synced copy of one backend catalogue item, keyed by its stable id. `groupId` is deliberately not a foreign key:
/// a newer backend may send a group this build has not seen, and the item must still be stored. The `override*`
/// columns are the item's own changes to its group's rules, null where the group's apply. `section` is the store
/// section the backend computed for the item, null until a sync delivers it.
class CatalogueItems extends Table {
  TextColumn get id => text()();
  TextColumn get name => text()();
  TextColumn get groupId => text()();
  TextColumn get form => text()();
  TextColumn get source => text()();
  RealColumn get densityGPerMl => real().nullable()();
  TextColumn get overrideTrackingMode => text().nullable()();
  TextColumn get overrideStockUnit => text().nullable()();
  IntColumn get overrideUnopenedShelfLifeDays => integer().nullable()();
  IntColumn get overrideOnceOpenedShelfLifeDays => integer().nullable()();
  TextColumn get section => text().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// The household's own changes to a catalogue item's rules, kept apart from the catalogue so a sync never erases
/// them: catalogue sync never writes this table. One row per item id, which may be a former id of a merged item;
/// every rule column is null where the household has not changed it.
class IngredientOverrides extends Table {
  TextColumn get itemId => text()();
  TextColumn get trackingMode => text().nullable()();
  TextColumn get stockUnit => text().nullable()();
  IntColumn get unopenedShelfLifeDays => integer().nullable()();
  IntColumn get onceOpenedShelfLifeDays => integer().nullable()();
  TextColumn get section => text().nullable()();

  @override
  Set<Column> get primaryKey => {itemId};
}

/// Maps the id of a catalogue item merged into another to the item that survives, so anything keyed by the old id
/// still resolves. Catalogue sync fills it.
class CatalogueItemRedirects extends Table {
  TextColumn get formerId => text()();
  TextColumn get itemId => text()();

  @override
  Set<Column> get primaryKey => {formerId};
}

/// Every name that resolves to a catalogue item, its canonical name included. `key` is the case-folded,
/// whitespace-collapsed form the backend sends for lookups.
class CatalogueAliases extends Table {
  TextColumn get key => text()();
  TextColumn get name => text()();
  TextColumn get itemId => text()();

  @override
  Set<Column> get primaryKey => {key};
}

/// How far catalogue sync has got: one row (`id` 1), absent until the first successful sync. `fullSyncedAt` is when
/// the last full (`since=0`) sync succeeded; ordinary delta syncs leave it alone, so they can never postpone the
/// next full one.
class CatalogueSyncState extends Table {
  IntColumn get id => integer()();
  IntColumn get version => integer()();
  TextColumn get syncedAt => text()();
  TextColumn get fullSyncedAt => text()();

  @override
  Set<Column> get primaryKey => {id};
}
