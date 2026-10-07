// The drift database for Glean. Local SQLite is the sole source of truth
// for user data (FLUTTER_MIGRATION.md §3) — there is no server-side user
// state to sync, so this file (plus the repositories in `repositories/`) is
// the entire persistence layer.
//
// Connection-agnostic on purpose: callers pass in a `QueryExecutor`, so
// production code wires up `drift_flutter`'s `driftDatabase()` (see
// `providers/database_providers.dart`) while tests use
// `NativeDatabase.memory()` (see `test/data/fixture.dart`). Both paths run
// the same `onCreate` seeding, so tests exercise the real seed data instead
// of a parallel fixture.
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
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (m) async {
        await m.createAll();
        await _seed();
      },
      onUpgrade: (m, from, to) async {
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
      },
      beforeOpen: (details) async {
        // SQLite disables foreign-key enforcement by default; the schema
        // relies on it for the `onDelete: cascade`/`setNull` behaviour that
        // backs AC-MEAL-03 and AC-SHOP-06.
        await customStatement('PRAGMA foreign_keys = ON');
      },
    );
  }

  // Seeds the 23-category taxonomy and 10 staples exactly once, on fresh
  // database creation (AC-DATA-10). No data migrates between users or
  // versions (FLUTTER_MIGRATION.md §1), so there is no "already seeded"
  // check to carry — `onCreate` only ever fires on a brand-new database.
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
