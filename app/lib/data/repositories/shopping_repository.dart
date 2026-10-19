// Shopping-list persistence.
//
// - `resolveCheckout` deletes only rows that are both checked and whose ingredient the receipt resolved, in
//   one statement scoped to the current user, so no unmatched, unchecked or other-user row is swept up.
// - `addManualItem` resolves an ingredient identity through `IngredientsRepository` so manual items can
//   match a receipt.
// - `addGapsForRecipe` records `sourceMealPlanEntryId`, so deleting that plan entry cascades its shopping
//   rows away.
import 'package:drift/drift.dart';

import '../database.dart';
import '../models/shopping_list_item_view.dart';
import '../models/store_section.dart';
import 'catalogue_repository.dart';
import 'ingredients_repository.dart';
import 'pantry_repository.dart' show PantryUnitMismatchException;
import '../util/recipe_servings.dart';
import '../util/unit_normalization.dart';

class ShoppingRepository {
  ShoppingRepository(this._db, this._ingredients)
    : _catalogue = CatalogueRepository(_db);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;
  final CatalogueRepository _catalogue;

  // Joining stock and cooking state makes demand react to either table, not
  // only to cart mutations. Physical rows retain per-meal cascade ownership.
  JoinedSelectStatement<HasResultSet, dynamic> _query(String userId) =>
      _db.select(_db.shoppingListItems).join([
          innerJoin(
            _db.ingredients,
            _db.ingredients.id.equalsExp(_db.shoppingListItems.ingredientId),
          ),
          // Not read: it makes the stream re-emit when a household override changes. The override itself is resolved
          // through the catalogue (see `_householdSections`), which also follows merged ids.
          leftOuterJoin(
            _db.ingredientOverrides,
            _db.ingredientOverrides.itemId.equalsExp(
              _db.ingredients.catalogueItemId,
            ),
          ),
          leftOuterJoin(
            _db.pantryItems,
            _db.pantryItems.userId.equalsExp(_db.shoppingListItems.userId) &
                _db.pantryItems.ingredientId.equalsExp(
                  _db.shoppingListItems.ingredientId,
                ),
          ),
          leftOuterJoin(
            _db.mealPlanEntries,
            _db.mealPlanEntries.id.equalsExp(
              _db.shoppingListItems.sourceMealPlanEntryId,
            ),
          ),
        ])
        ..where(_db.shoppingListItems.userId.equals(userId))
        ..orderBy([OrderingTerm.asc(_db.shoppingListItems.id)]);

  Stream<List<ShoppingListItemView>> watchAll(String userId) =>
      _query(userId).watch().asyncMap(_resolveVisible);

  Future<List<ShoppingListItemView>> _resolveVisible(
    List<TypedResult> rows,
  ) async => _visible(rows, await _householdSections(rows));

  // The household's chosen section label for each catalogue item the rows' ingredients are linked to, through the
  // same resolver `effectiveIngredient` uses, so the two can never disagree.
  Future<Map<String, String>> _householdSections(List<TypedResult> rows) async {
    final itemIds = <String>{
      for (final joined in rows)
        ?joined.readTable(_db.ingredients).catalogueItemId,
    };
    final sections = <String, String>{};
    for (final id in itemIds) {
      final label = await _catalogue.householdSection(id);
      if (label != null) sections[id] = label;
    }
    return sections;
  }

  List<ShoppingListItemView> _visible(
    List<TypedResult> rows,
    Map<String, String> householdSections,
  ) {
    final canonicalUnits = <int, String?>{};
    final remainingStock = <(int, String?), double>{};
    final grouped = <(int, String?, bool), ShoppingListItemView>{};
    final result = <ShoppingListItemView>[];
    for (final joined in rows) {
      final row = joined.readTable(_db.shoppingListItems);
      final ingredient = joined.readTable(_db.ingredients);
      final meal = joined.readTableOrNull(_db.mealPlanEntries);
      if (!row.isRequirement) {
        // Plan-gap rows written before requirement rows existed keep their own quantity, but still name the
        // planned recipe from the entry's title snapshot.
        result.add(
          _mapRow(
            row,
            ingredient,
            householdSections,
            recipeTitles: [if (meal != null) meal.recipeTitle],
          ),
        );
        continue;
      }
      if (meal == null || meal.cookedAt != null) continue;
      final stock = joined.readTableOrNull(_db.pantryItems);
      // Compatible demands share a single stock budget, even when a unit edit
      // leaves older rows in mass and newer rows in convertible volume units.
      final canonical = canonicalUnits.putIfAbsent(
        row.ingredientId,
        () => row.unit,
      );
      final requirement = normalizeUnit(
        quantity: row.quantity ?? 0,
        unit: row.unit ?? 'units',
        canonicalUnit: canonical,
        canonicalName: row.name,
      );
      final unit = requirement?.unit ?? row.unit;
      final stockKey = (row.ingredientId, unit);
      final available = remainingStock.putIfAbsent(
        stockKey,
        () => stock == null
            ? 0
            : normalizeUnit(
                    quantity: stock.quantity,
                    unit: stock.unit,
                    canonicalUnit: unit,
                    canonicalName: row.name,
                  )?.quantity ??
                  0,
      );
      final needed = requirement?.quantity ?? row.quantity ?? 0;
      final used = available.clamp(0.0, needed);
      remainingStock[stockKey] = available - used;
      final missing = needed - used;
      if (missing <= 0) continue;
      final key = (row.ingredientId, unit, row.isChecked);
      final prior = grouped[key];
      grouped[key] = _mapRow(
        row,
        ingredient,
        householdSections,
        quantity: missing + (prior?.quantity ?? 0),
        unit: unit,
        memberIds: [...?prior?.ids, row.id],
        recipeTitles: [
          ...?prior?.recipeTitles,
          if (!(prior?.recipeTitles.contains(meal.recipeTitle) ?? false))
            meal.recipeTitle,
        ],
      );
    }
    result.addAll(grouped.values);
    result.sort(
      (a, b) => a.isChecked != b.isChecked
          ? (a.isChecked ? 1 : -1)
          : b.id.compareTo(a.id),
    );
    return result;
  }

  ShoppingListItemView _mapRow(
    ShoppingListItem row,
    Ingredient ingredient,
    Map<String, String> householdSections, {
    double? quantity,
    String? unit,
    List<int> memberIds = const [],
    List<String> recipeTitles = const [],
  }) => ShoppingListItemView(
    id: row.id,
    userId: row.userId,
    ingredientId: row.ingredientId,
    name: row.name,
    quantity: quantity ?? row.quantity,
    unit: unit ?? row.unit,
    source: ShoppingSource.fromDb(row.source),
    isChecked: row.isChecked,
    sourceMealPlanEntryId: memberIds.length > 1
        ? null
        : row.sourceMealPlanEntryId,
    section: resolveStoreSection(
      name: ingredient.canonicalName,
      groupId: ingredient.groupId,
      override: _chosenSection(ingredient, householdSections),
    ),
    memberIds: memberIds,
    recipeTitles: recipeTitles,
  );

  // The household's own store section for an ingredient: the one in its catalogue item's override, else the choice
  // still held on the ingredient (an ingredient with no item yet, or one whose choice the override could not take).
  StoreSection? _chosenSection(
    Ingredient ingredient,
    Map<String, String> householdSections,
  ) {
    final String? itemId = ingredient.catalogueItemId;
    final String? label = itemId == null ? null : householdSections[itemId];
    if (label != null) {
      return StoreSection.values.firstWhere((s) => s.label == label);
    }
    final String? held = ingredient.storeSection;
    return held == null ? null : StoreSection.fromDb(held);
  }

  /// Adds a manual entry, resolving [name] to a real ingredient identity so it can match a receipt at
  /// checkout. No LLM classification, so the group is left untouched (or unclassified if new).
  ///
  /// [unit], when given, also seeds/upgrades `canonicalUnit` via `IngredientsRepository.resolveOrCreate`: a
  /// manual entry's unit is a real stock-tracking unit, unlike a recipe's.
  Future<int> addManualItem({
    required String userId,
    required String name,
    double? quantity,
    String? unit,
  }) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError.value(name, 'name', 'cannot be empty');
    }
    final ingredient = await _ingredients.resolveOrCreate(
      canonicalName: trimmed,
      unit: unit,
    );
    return _db
        .into(_db.shoppingListItems)
        .insert(
          ShoppingListItemsCompanion.insert(
            userId: userId,
            ingredientId: ingredient.id,
            name: trimmed,
            quantity: Value(quantity),
            unit: Value(unit?.trim()),
          ),
        );
  }

  /// Adds AI-parsed items, each resolved to a real ingredient identity with the backend's ingredient group. A parsed
  /// unit seeds/upgrades `canonicalUnit` only when genuinely non-blank: a blank one defaults to `'units'` for the
  /// row but must never become the ingredient's permanent canonical unit. Runs as a single transaction, so a
  /// failure persists nothing and retrying can't double-insert.
  Future<void> addAiItems({
    required String userId,
    required List<AiShoppingItem> items,
  }) {
    return _db.transaction(() async {
      for (final item in items) {
        final name = item.name.trim();
        if (name.isEmpty) continue;
        final String trimmedUnit = item.unit.trim();
        final String unit = trimmedUnit.isEmpty ? 'units' : trimmedUnit;
        final ingredient = await _ingredients.resolveOrCreate(
          canonicalName: name,
          groupId: item.groupId,
          unit: trimmedUnit.isEmpty ? null : trimmedUnit,
        );
        await _db
            .into(_db.shoppingListItems)
            .insert(
              ShoppingListItemsCompanion.insert(
                userId: userId,
                ingredientId: ingredient.id,
                name: name,
                quantity: Value(item.quantity),
                unit: Value(unit),
                source: Value(ShoppingSource.ai.dbValue),
              ),
            );
      }
    });
  }

  /// Stores each meal's full non-optional requirement. The read model allocates
  /// pantry stock once and aggregates the visible deficits; stock-satisfied
  /// requirements are retained invisibly so another meal cannot reuse them.
  ///
  /// Returns the number of newly visible requirement rows so a caller can announce the outcome.
  ///
  /// Idempotency is scoped to the same meal's requirement. A different meal
  /// must retain its own row so deleting one cannot erase another's demand.
  Future<int> addGapsForRecipe({
    required String userId,
    required int recipeId,
    required int servings,
    required int sourceMealPlanEntryId,
  }) => _db.transaction(() async {
    final recipe =
        await (_db.select(_db.recipes)
              ..where((t) => t.id.equals(recipeId) & t.userId.equals(userId)))
            .getSingle();
    final before = (await _resolveVisible(
      await _query(userId).get(),
    )).expand((item) => item.ids).toSet();
    final requirements =
        <int, ({Ingredient ingredient, double quantity, String unit})>{};
    final rows =
        await (_db.select(_db.recipeIngredients).join([
              innerJoin(
                _db.ingredients,
                _db.ingredients.id.equalsExp(
                  _db.recipeIngredients.ingredientId,
                ),
              ),
            ])..where(
              _db.recipeIngredients.recipeId.equals(recipeId) &
                  _db.recipeIngredients.isOptional.equals(false),
            ))
            .get();

    for (final row in rows) {
      final recipeIngredient = row.readTable(_db.recipeIngredients);
      final ingredient = row.readTable(_db.ingredients);
      final pantryRow =
          await (_db.select(_db.pantryItems)..where(
                (t) =>
                    t.userId.equals(userId) &
                    t.ingredientId.equals(recipeIngredient.ingredientId),
              ))
              .getSingleOrNull();
      final unit = canonicalUnitFor(pantryRow?.unit ?? recipeIngredient.unit);
      final normalized = normalizeUnit(
        quantity: recipeQuantityForServings(
          quantity: recipeIngredient.quantity,
          servings: servings,
          yieldCount: recipe.yieldCount,
        ),
        unit: recipeIngredient.unit,
        canonicalUnit: unit,
        canonicalName: ingredient.canonicalName,
      );
      if (normalized == null) {
        throw PantryUnitMismatchException(
          ingredientId: ingredient.id,
          canonicalName: ingredient.canonicalName,
          existingUnit: unit,
          incomingUnit: recipeIngredient.unit,
        );
      }
      final prior = requirements[ingredient.id];
      requirements[ingredient.id] = (
        ingredient: ingredient,
        quantity: normalized.quantity + (prior?.quantity ?? 0),
        unit: unit,
      );
    }
    for (final requirement in requirements.values) {
      final ingredient = requirement.ingredient;
      final existing =
          await (_db.select(_db.shoppingListItems)..where(
                (t) =>
                    t.userId.equals(userId) &
                    t.ingredientId.equals(ingredient.id) &
                    t.sourceMealPlanEntryId.equals(sourceMealPlanEntryId),
              ))
              .getSingleOrNull();
      if (existing != null) continue;

      await _db
          .into(_db.shoppingListItems)
          .insert(
            ShoppingListItemsCompanion.insert(
              userId: userId,
              ingredientId: ingredient.id,
              name: ingredient.canonicalName,
              quantity: Value(requirement.quantity),
              unit: Value(requirement.unit),
              source: Value(ShoppingSource.mealPlan.dbValue),
              isRequirement: const Value(true),
              sourceMealPlanEntryId: Value(sourceMealPlanEntryId),
            ),
          );
    }
    return (await _resolveVisible(
      await _query(userId).get(),
    )).expand((item) => item.ids).where((id) => !before.contains(id)).length;
  });

  Future<List<ShoppingListItem>> deleteRowsWithSnapshot({
    required List<int> ids,
    required String userId,
  }) => _db.transaction(() async {
    final rows = await (_db.select(
      _db.shoppingListItems,
    )..where((t) => t.id.isIn(ids) & t.userId.equals(userId))).get();
    await (_db.delete(
      _db.shoppingListItems,
    )..where((t) => t.id.isIn(ids) & t.userId.equals(userId))).go();
    return rows;
  });

  Future<void> restoreRows({
    required List<ShoppingListItem> rows,
    required String userId,
  }) => _db.transaction(() async {
    for (final row in rows) {
      if (row.userId != userId) {
        throw ArgumentError('Undo belongs to another user');
      }
      if (row.sourceMealPlanEntryId != null &&
          await (_db.select(_db.mealPlanEntries)..where(
                    (t) =>
                        t.id.equals(row.sourceMealPlanEntryId!) &
                        t.userId.equals(userId),
                  ))
                  .getSingleOrNull() ==
              null) {
        continue;
      }
      await _db.into(_db.shoppingListItems).insert(row.toCompanion(false));
    }
  });

  /// Moves every row of [ingredientId] (now and later) to [section]. The choice belongs to the ingredient, so
  /// it also applies to rows added afterwards.
  ///
  /// An ingredient with a catalogue item keeps the choice in that item's override, beside the household's other changes
  /// to it, so it follows the item; one without keeps it on the ingredient until it is linked.
  Future<void> moveToSection({
    required int ingredientId,
    required StoreSection section,
  }) => _db.transaction(() async {
    final ingredient = await (_db.select(
      _db.ingredients,
    )..where((t) => t.id.equals(ingredientId))).getSingle();
    final String? itemId = ingredient.catalogueItemId;
    if (itemId == null) {
      await (_db.update(_db.ingredients)
            ..where((t) => t.id.equals(ingredientId)))
          .write(IngredientsCompanion(storeSection: Value(section.dbValue)));
      return;
    }
    await _db
        .into(_db.ingredientOverrides)
        .insert(
          IngredientOverridesCompanion.insert(
            itemId: itemId,
            section: Value(section.label),
          ),
          onConflict: DoUpdate(
            (_) => IngredientOverridesCompanion(section: Value(section.label)),
            target: [_db.ingredientOverrides.itemId],
          ),
        );
    await (_db.update(_db.ingredients)..where((t) => t.id.equals(ingredientId)))
        .write(const IngredientsCompanion(storeSection: Value(null)));
  });

  Future<void> toggleRows({
    required List<int> ids,
    required String userId,
    required bool checked,
  }) =>
      (_db.update(_db.shoppingListItems)
            ..where((t) => t.id.isIn(ids) & t.userId.equals(userId)))
          .write(ShoppingListItemsCompanion(isChecked: Value(checked)));

  /// Completes a checkout backed by a scanned receipt: removes only the checked rows whose ingredient the
  /// receipt resolved, leaving every other row as it was. `userId` + `isChecked` + a matched `ingredientId` in
  /// one statement means there is no separate tick step whose scoping could go wrong.
  Future<int> resolveCheckout({
    required String userId,
    required List<int> resolvedIngredientIds,
  }) {
    if (resolvedIngredientIds.isEmpty) return Future.value(0);
    return (_db.delete(_db.shoppingListItems)..where(
          (t) =>
              t.userId.equals(userId) &
              t.ingredientId.isIn(resolvedIngredientIds) &
              t.isChecked.equals(true),
        ))
        .go();
  }
}

class AiShoppingItem {
  const AiShoppingItem({
    required this.name,
    required this.quantity,
    required this.unit,
    this.groupId,
  });

  final String name;
  final double quantity;
  final String unit;
  final String? groupId;
}
