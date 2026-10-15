// The drift database for Glean. Local SQLite is the sole source of user data.
//
// Connection-agnostic: callers pass a `QueryExecutor` (production: `driftDatabase()` in
// `providers/database_providers.dart`; tests: `NativeDatabase.memory()`), and both run the same `onCreate`
// seeding.
import 'package:drift/drift.dart';

import 'seed/taxonomy.dart';
import 'tables.dart';

part 'database.g.dart';

@DriftDatabase(
  tables: [
    IngredientCategories,
    Ingredients,
    PantryItems,
    Recipes,
    RecipeDietaryFlags,
    RecipeIngredients,
    MealPlanEntries,
    CookedAdjustments,
    ShoppingListItems,
    UserConfig,
  ],
)
class GleanDatabase extends _$GleanDatabase {
  GleanDatabase(super.executor);

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (m) async {
        await m.createAll();
        await _seed();
      },
      onUpgrade: (m, from, to) async {
        // A database written by a newer build: opening it here would skip
        // that build's migrations and break the next upgrade, so refuse and
        // leave the file as it is (the user's only copy of their data).
        if (from > to) {
          throw StateError(
            'Database schema v$from is newer than this build (v$to); '
            'install the latest build instead.',
          );
        }
        if (from < 2) {
          await m.addColumn(
            mealPlanEntries,
            mealPlanEntries.externalIdSnapshot,
          );
          await m.addColumn(
            mealPlanEntries,
            mealPlanEntries.previousRecipeCookedAt,
          );
          await m.addColumn(shoppingListItems, shoppingListItems.isRequirement);
          await customStatement(
            'UPDATE meal_plan_entries SET external_id_snapshot = (SELECT external_id FROM recipes WHERE recipes.id = meal_plan_entries.recipe_id)',
          );
        }
        if (from < 3) {
          await m.addColumn(ingredients, ingredients.storeSection);
          await m.addColumn(userConfig, userConfig.groupShoppingBySection);
        }
      },
      beforeOpen: (details) async {
        // SQLite disables foreign-key enforcement by default; the schema relies on it for
        // `onDelete: cascade`/`setNull`.
        await customStatement('PRAGMA foreign_keys = ON');
      },
    );
  }

  // Seeds the 23-category taxonomy and 10 staples on fresh database creation; `onCreate` only fires on a
  // brand-new database.
  Future<void> _seed() async {
    await batch((b) {
      b.insertAll(ingredientCategories, [
        for (final seed in ingredientCategorySeeds)
          IngredientCategoriesCompanion.insert(
            category: seed.category,
            foodGroup: seed.foodGroup,
            shelfLifeDays: seed.shelfLifeDays,
          ),
      ]);
      b.insertAll(ingredients, [
        for (final staple in stapleSeeds)
          IngredientsCompanion.insert(
            canonicalName: staple.canonicalName,
            category: Value(staple.category),
            isStaple: const Value(true),
          ),
      ]);
    });
  }
}

/// Closes [db], even while screens still hold stream subscriptions.
///
/// drift awaits inside a loop over its active streams, and a subscriber cancelling at the same moment changes
/// that collection and throws [ConcurrentModificationError] before the connection is closed. The streams are
/// gone by the second attempt, so a retry completes the close.
Future<void> closeDatabase(GleanDatabase db) async {
  for (var attempt = 0; ; attempt++) {
    try {
      await db.close();
      return;
    } on ConcurrentModificationError {
      if (attempt >= 2) rethrow;
    }
  }
}
