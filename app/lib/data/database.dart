// The drift database for Glean. Local SQLite is the sole source of user data.
//
// Connection-agnostic: callers pass a `QueryExecutor` (production: `driftDatabase()` in
// `providers/database_providers.dart`; tests: `NativeDatabase.memory()`), and both run the same `onCreate`
// seeding.
import 'dart:convert';

import 'package:drift/drift.dart';

import 'seed/ingredient_groups.dart';
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
    IngredientGroups,
    CatalogueItems,
    CatalogueAliases,
    CatalogueSyncState,
    IngredientOverrides,
    CatalogueItemRedirects,
  ],
)
class GleanDatabase extends _$GleanDatabase {
  GleanDatabase(super.executor);

  @override
  int get schemaVersion => 5;

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (m) async {
        await m.createAll();
        await _seed();
        await _seedIngredientGroups();
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
        if (from < 4) {
          await _addCatalogueTables(m);
        }
        if (from < 5) {
          await _addOverrideTables(m);
        }
      },
      beforeOpen: (details) async {
        // SQLite disables foreign-key enforcement by default; the schema relies on it for
        // `onDelete: cascade`/`setNull`.
        await customStatement('PRAGMA foreign_keys = ON');
      },
    );
  }

  // The catalogue's tables, additive only: nothing here touches an older table. Self-contained so it can be
  // renumbered by changing only the `from <` guard that calls it.
  Future<void> _addCatalogueTables(Migrator m) async {
    await m.createTable(ingredientGroups);
    await m.createTable(catalogueItems);
    await m.createTable(catalogueAliases);
    await m.createTable(catalogueSyncState);
    await _seedIngredientGroups();
  }

  // Household overrides, merged-id redirects and each item's synced section, additive only. Self-contained so it can
  // be renumbered by changing only the `from <` guard that calls it. Items keep a null section until the next sync.
  // A file older than v4 has just had `catalogue_items` created in its current shape, which already has `section`.
  Future<void> _addOverrideTables(Migrator m) async {
    final columns = await customSelect(
      'PRAGMA table_info(catalogue_items)',
    ).get();
    if (!columns.any((c) => c.read<String>('name') == 'section')) {
      await m.addColumn(catalogueItems, catalogueItems.section);
    }
    await m.createTable(ingredientOverrides);
    await m.createTable(catalogueItemRedirects);
  }

  // The groups the app works from before its first sync. A sync later overwrites them by id.
  Future<void> _seedIngredientGroups() async {
    await batch((b) {
      b.insertAll(ingredientGroups, [
        for (final seed in ingredientGroupSeeds)
          IngredientGroupsCompanion.insert(
            id: seed.id,
            name: seed.name,
            kind: seed.kind,
            foodGroup: seed.foodGroup,
            trackingMode: seed.trackingMode,
            stockUnit: Value(seed.stockUnit),
            allowedForms: jsonEncode(seed.allowedForms),
            unopenedShelfLifeDays: jsonEncode(seed.unopenedShelfLifeDays),
            onceOpenedShelfLifeDays: jsonEncode(seed.onceOpenedShelfLifeDays),
          ),
      ]);
    });
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
