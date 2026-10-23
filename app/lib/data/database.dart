// The drift database for Glean. Local SQLite is the sole source of user data.
//
// Connection-agnostic: callers pass a `QueryExecutor` (production: `driftDatabase()` in
// `providers/database_providers.dart`; tests: `NativeDatabase.memory()`), and both run the same `onCreate`
// seeding.
import 'dart:convert';

import 'package:drift/drift.dart';

import 'seed/ingredient_groups.dart';
import 'models/store_section.dart';
import 'seed/taxonomy.dart';
import 'tables.dart';

part 'database.g.dart';

/// A name as `catalogue_aliases.key` holds it: case-folded and whitespace-collapsed, as the backend sends it.
String catalogueNameKey(String name) => name
    .toLowerCase()
    .split(RegExp(r'\s+'))
    .where((w) => w.isNotEmpty)
    .join(' ');

@DriftDatabase(
  tables: [
    Ingredients,
    PantryItems,
    Recipes,
    RecipeDietaryFlags,
    RecipeIngredients,
    MealPlanEntries,
    MealRatings,
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
  int get schemaVersion => 7;

  @override
  MigrationStrategy get migration {
    return MigrationStrategy(
      onCreate: (m) async {
        await m.createAll();
        await _seedIngredientGroups();
        await _seedStaples();
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
        // One transaction for the whole upgrade, so a failure part-way leaves the file at the version it was.
        await transaction(() async {
          if (from < 2) {
            await m.addColumn(
              mealPlanEntries,
              mealPlanEntries.externalIdSnapshot,
            );
            await m.addColumn(
              mealPlanEntries,
              mealPlanEntries.previousRecipeCookedAt,
            );
            await m.addColumn(
              shoppingListItems,
              shoppingListItems.isRequirement,
            );
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
          if (from < 6) {
            await _moveIngredientsToGroups(m);
          }
          if (from < 7) {
            await _addMealRatings(m);
          }
        });
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

  // Moves ingredients from the 23 old categories onto ingredient groups: `category` becomes `group_id` (see
  // `legacyCategoryGroups`; a null or unknown category becomes Other, so no row is dropped), `api_ingredient_id` goes,
  // and the nullable `catalogue_item_id` and `form` arrive empty. Then links what the catalogue already names. Safe to
  // run again: a table already on groups is left alone, and the old category table holds only seed data.
  Future<void> _moveIngredientsToGroups(Migrator m) async {
    final columns = await customSelect('PRAGMA table_info(ingredients)').get();
    if (!columns.any((c) => c.read<String>('name') == 'group_id')) {
      final cases = [
        for (final e in legacyCategoryGroups.entries)
          "WHEN '${e.key}' THEN '${e.value}'",
      ].join(' ');
      await m.alterTable(
        TableMigration(
          ingredients,
          columnTransformer: {
            ingredients.groupId: CustomExpression(
              'CASE "category" $cases ELSE \'$otherGroupId\' END',
            ),
          },
          newColumns: [
            ingredients.groupId,
            ingredients.catalogueItemId,
            ingredients.form,
          ],
        ),
      );
    }
    await customStatement('DROP TABLE IF EXISTS ingredient_categories');
    await linkIngredientsToCatalogue();
  }

  /// Links every ingredient that has no catalogue item yet to the one its name matches, by canonical name or alias
  /// (`catalogue_aliases` holds both, case-folded and whitespace-collapsed), following a merged item to the item that
  /// survives. An ingredient whose name matches nothing stays unlinked and keeps working. Moves a linked ingredient's
  /// own store-section choice into `ingredient_overrides`, beside the override's other changes. Run when the app
  /// upgrades and after every catalogue sync, so it is idempotent; it never overwrites a section already held there.
  /// [ingredientId] limits it to one ingredient, for one just created.
  Future<void> linkIngredientsToCatalogue({int? ingredientId}) => transaction(
    () async {
      if (ingredientId == null) await _repointLinksToSurvivors();
      final unlinked =
          await (select(ingredients)..where(
                (t) =>
                    t.catalogueItemId.isNull() &
                    (ingredientId == null
                        ? const Constant(true)
                        : t.id.equals(ingredientId)),
              ))
              .get();
      if (unlinked.isEmpty) return;
      final keyOf = {
        for (final i in unlinked) i.id: catalogueNameKey(i.canonicalName),
      };
      final itemByKey = <String, String>{};
      final keys = keyOf.values.toSet().toList();
      for (var start = 0; start < keys.length; start += 500) {
        final chunk = keys.sublist(start, (start + 500).clamp(0, keys.length));
        final aliases = await (select(
          catalogueAliases,
        )..where((t) => t.key.isIn(chunk))).get();
        for (final a in aliases) {
          itemByKey[a.key] = a.itemId;
        }
      }
      for (final ingredient in unlinked) {
        final aliasItem = itemByKey[keyOf[ingredient.id]];
        if (aliasItem == null) continue;
        final itemId = await survivingCatalogueItemId(aliasItem);
        final item = await (select(
          catalogueItems,
        )..where((t) => t.id.equals(itemId))).getSingleOrNull();
        if (item == null) continue;
        final choice = _storeSectionLabel(ingredient.storeSection);
        final bool moved =
            choice != null && await _moveSectionChoice(itemId, choice);
        await (update(
          ingredients,
        )..where((t) => t.id.equals(ingredient.id))).write(
          IngredientsCompanion(
            catalogueItemId: Value(itemId),
            storeSection: moved ? const Value(null) : const Value.absent(),
          ),
        );
      }
    },
  );

  // An ingredient linked to a former id of a merged item is moved to the item that survives. That is the app's own
  // derived link; no household override is read or written here.
  Future<void> _repointLinksToSurvivors() async {
    final stale =
        await (select(ingredients)..where(
              (t) => t.catalogueItemId.isInQuery(
                selectOnly(catalogueItemRedirects)
                  ..addColumns([catalogueItemRedirects.formerId]),
              ),
            ))
            .get();
    for (final ingredient in stale) {
      final survivor = await survivingCatalogueItemId(
        ingredient.catalogueItemId!,
      );
      if (survivor == ingredient.catalogueItemId) continue;
      final item = await (select(
        catalogueItems,
      )..where((t) => t.id.equals(survivor))).getSingleOrNull();
      if (item == null) continue;
      await (update(ingredients)..where((t) => t.id.equals(ingredient.id)))
          .write(IngredientsCompanion(catalogueItemId: Value(survivor)));
    }
  }

  /// Every id that names the same catalogue item as [survivorId]: itself and each former id merged into it, directly
  /// or through earlier merges.
  Future<Set<String>> catalogueIdentity(String survivorId) async {
    final ids = <String>[survivorId];
    for (var i = 0; i < ids.length; i++) {
      final formers = await (select(
        catalogueItemRedirects,
      )..where((t) => t.itemId.equals(ids[i]))).get();
      for (final r in formers) {
        if (!ids.contains(r.formerId)) ids.add(r.formerId);
      }
    }
    return ids.toSet();
  }

  /// The surviving catalogue item a name or alias resolves to, or null when the catalogue holds none for it. A name
  /// is matched as the catalogue matches it (see [catalogueNameKey]) and a merged item is followed to the one that
  /// survives.
  Future<String?> catalogueItemIdForName(String name) async {
    final alias = await (select(
      catalogueAliases,
    )..where((t) => t.key.equals(catalogueNameKey(name)))).getSingleOrNull();
    if (alias == null) return null;
    final itemId = await survivingCatalogueItemId(alias.itemId);
    final item = await (select(
      catalogueItems,
    )..where((t) => t.id.equals(itemId))).getSingleOrNull();
    return item?.id;
  }

  // The label `ingredient_overrides.section` holds for a stored `StoreSection.dbValue`; null when there is no choice or
  // the value is one this build doesn't know, which is then left where it is rather than guessed at.
  String? _storeSectionLabel(String? dbValue) {
    for (final section in StoreSection.values) {
      if (section.dbValue == dbValue) return section.label;
    }
    return null;
  }

  // Writes [label] as the section of the item's override unless the household already chose another one there.
  // Returns whether the choice is now held by the override, so the caller may clear its own copy.
  Future<bool> _moveSectionChoice(String itemId, String label) async {
    final existing = await (select(
      ingredientOverrides,
    )..where((t) => t.itemId.equals(itemId))).getSingleOrNull();
    if (existing == null) {
      await into(ingredientOverrides).insert(
        IngredientOverridesCompanion.insert(
          itemId: itemId,
          section: Value(label),
        ),
      );
      return true;
    }
    if (existing.section == null) {
      await (update(ingredientOverrides)..where((t) => t.itemId.equals(itemId)))
          .write(IngredientOverridesCompanion(section: Value(label)));
      return true;
    }
    return existing.section == label;
  }

  /// Follows a merged item to the item that survives; a cycle stops at the first id seen twice.
  Future<String> survivingCatalogueItemId(String id) async {
    final seen = <String>{id};
    var current = id;
    while (true) {
      final redirect = await (select(
        catalogueItemRedirects,
      )..where((t) => t.formerId.equals(current))).getSingleOrNull();
      if (redirect == null || !seen.add(redirect.itemId)) return current;
      current = redirect.itemId;
    }
  }

  // Ratings and the flag for their one-off explainer, additive only. A file upgrading from v6 keeps every
  // plan entry and gains an empty `meal_ratings` table; the flag defaults false, so the explainer is shown
  // once on the first thumb after the upgrade. Self-contained so it can be renumbered by changing only the
  // `from <` guard that calls it.
  //
  // Each part is guarded by what the file already holds, so replaying the step over an upgraded database
  // changes nothing rather than failing on a table or column that is already there.
  Future<void> _addMealRatings(Migrator m) async {
    final ratings = await customSelect(
      "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'meal_ratings'",
    ).get();
    if (ratings.isEmpty) await m.createTable(mealRatings);
    final columns = await customSelect('PRAGMA table_info(user_config)').get();
    if (!columns.any(
      (c) => c.read<String>('name') == 'ratings_explainer_seen',
    )) {
      await m.addColumn(userConfig, userConfig.ratingsExplainerSeen);
    }
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

  // Seeds the 10 staples on fresh database creation; `onCreate` only fires on a brand-new database.
  Future<void> _seedStaples() async {
    await batch((b) {
      b.insertAll(ingredients, [
        for (final staple in stapleSeeds)
          IngredientsCompanion.insert(
            canonicalName: staple.canonicalName,
            groupId: Value(staple.groupId),
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
