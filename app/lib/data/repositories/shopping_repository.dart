// Ported from the Expo app's `src/db/shopping.ts` (see git history),
// fixing the three data-integrity bugs FLUTTER_MIGRATION.md §11/§6 Shop
// call out:
//
//   - `resolveCheckout` (AC-SHOP-01/AC-SHOP-04) replaces both `completeCheckout`
//     *and* `checkOffByIngredientIds`. `completeCheckout` deleted *every*
//     checked row regardless of receipt match — check off 12 items, scan a
//     receipt matching 4, and the other 8 vanished without ever becoming
//     pantry stock. `resolveCheckout` deletes only rows that are both
//     checked *and* whose ingredient the receipt actually resolved, in one
//     statement scoped to the current user — so there is no window where an
//     unmatched checked row, an unchecked row, or another user's row could
//     be swept up.
//
//     RN's flow was two steps for a reason this port's isn't: `checkOffByIngredientIds`
//     first ticked every row the receipt resolved (whether or not the user
//     had checked it), then `completeCheckout` deleted every checked row —
//     so an unscoped/unchecked-row bug in *either* step could corrupt the
//     list. Collapsing both into `resolveCheckout`'s single atomic,
//     already-scoped statement made the standalone tick step (`AC-SHOP-04`
//     required by-ingredient check-off to be scoped) genuinely redundant —
//     ported once as `checkOffResolvedIngredients`, unit-tested, but never
//     called from anywhere real — so R-03 deleted it rather than wiring a
//     second, needless path to the same rows. AC-SHOP-04 is satisfied by
//     `resolveCheckout`'s own scoping (`userId` + `isChecked` + a matched
//     `ingredientId`) instead.
//   - `addManualItem` (AC-SHOP-03) resolves an ingredient identity through
//     `IngredientsRepository` instead of storing `ingredient_id: null`,
//     which is why manual items never matched a receipt in RN.
//
// `addGapsForRecipe` also records `sourceMealPlanEntryId`, so deleting that
// plan entry cascades its shopping rows away (AC-SHOP-06) via the schema's
// `onDelete: cascade` rather than a manual sweep.
import 'package:drift/drift.dart';

import '../database.dart';
import '../models/shopping_list_item_view.dart';
import 'ingredients_repository.dart';
import 'pantry_repository.dart' show PantryUnitMismatchException;
import '../util/recipe_servings.dart';
import '../util/unit_normalization.dart';

class ShoppingRepository {
  ShoppingRepository(this._db, this._ingredients);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;

  // Joining stock and cooking state makes demand react to either table, not
  // only to cart mutations. Physical rows retain per-meal cascade ownership.
  JoinedSelectStatement<HasResultSet, dynamic> _query(String userId) =>
      _db.select(_db.shoppingListItems).join([
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
      _query(userId).watch().map(_visible);

  List<ShoppingListItemView> _visible(List<TypedResult> rows) {
    final canonicalUnits = <int, String?>{};
    final remainingStock = <(int, String?), double>{};
    final grouped = <(int, String?, bool), ShoppingListItemView>{};
    final result = <ShoppingListItemView>[];
    for (final joined in rows) {
      final row = joined.readTable(_db.shoppingListItems);
      if (!row.isRequirement) {
        result.add(_mapRow(row));
        continue;
      }
      final meal = joined.readTableOrNull(_db.mealPlanEntries);
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
        quantity: missing + (prior?.quantity ?? 0),
        unit: unit,
        memberIds: [...?prior?.ids, row.id],
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
    ShoppingListItem row, {
    double? quantity,
    String? unit,
    List<int> memberIds = const [],
  }) => ShoppingListItemView(
    id: row.id,
    userId: row.userId,
    ingredientId: row.ingredientId,
    name: row.name,
    quantity: quantity ?? row.quantity,
    unit: unit ?? row.unit,
    source: row.source,
    isChecked: row.isChecked,
    sourceMealPlanEntryId: memberIds.length > 1
        ? null
        : row.sourceMealPlanEntryId,
    memberIds: memberIds,
  );

  /// Adds a manual entry, resolving [name] to a real ingredient identity
  /// (AC-SHOP-03) so it can later match a receipt at checkout. [category]
  /// is optional — a manual entry has no LLM classification behind it, so
  /// unlike pantry intake this does not require one; if the ingredient
  /// already exists with a category, that is left untouched, and if not, it
  /// simply stays uncategorised until something else resolves it.
  ///
  /// [unit], when given, also seeds/upgrades `canonicalUnit` (R-18) via
  /// `IngredientsRepository.resolveOrCreate` — a manual shopping entry is a
  /// real stock-tracking unit like a pantry add, unlike a recipe's.
  Future<int> addManualItem({
    required String userId,
    required String name,
    double? quantity,
    String? unit,
    String? category,
  }) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError.value(name, 'name', 'cannot be empty');
    }
    final ingredient = await _ingredients.resolveOrCreate(
      canonicalName: trimmed,
      category: category,
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

  /// Adds AI-parsed items (receipt describe / shopping description parse),
  /// each resolved to a real ingredient identity with the category the
  /// backend returned (§9), also seeding/upgrading `canonicalUnit` (R-18)
  /// from its parsed unit for the same reason — but, per R-23, only when
  /// [AiShoppingItem.unit] is genuinely non-blank. A blank one still
  /// defaults to `'units'` for the row itself (every row needs some unit
  /// string), but that fallback must never become the ingredient's
  /// *permanent* canonical unit — only an explicitly parsed/typed one
  /// should. Runs as a single transaction (AC-PAN-10): a failure partway
  /// through the list persists nothing, so retrying can't double-insert the
  /// rows that already succeeded.
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
          apiIngredientId: item.apiIngredientId,
          category: item.category,
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
                source: const Value('ai'),
              ),
            );
      }
    });
  }

  /// Stores each meal's full non-optional requirement. The read model allocates
  /// pantry stock once and aggregates the visible deficits; stock-satisfied
  /// requirements are retained invisibly so another meal cannot reuse them.
  ///
  /// Returns the number of newly visible requirement rows, so a caller can announce
  /// the outcome (AC-SHOP-05 — plan-derived rows must be announced, not
  /// inserted silently) rather than assuming something happened.
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
    final before = _visible(
      await _query(userId).get(),
    ).expand((item) => item.ids).toSet();
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
              source: const Value('meal_plan'),
              isRequirement: const Value(true),
              sourceMealPlanEntryId: Value(sourceMealPlanEntryId),
            ),
          );
    }
    return _visible(
      await _query(userId).get(),
    ).expand((item) => item.ids).where((id) => !before.contains(id)).length;
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

  Future<List<ShoppingListItem>> deleteCheckedWithSnapshot({
    required String userId,
  }) => _db.transaction(() async {
    final rows = await (_db.select(
      _db.shoppingListItems,
    )..where((t) => t.isChecked.equals(true) & t.userId.equals(userId))).get();
    await completeCheckoutWithoutReceipt(userId: userId);
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

  Future<void> toggleRows({
    required List<int> ids,
    required String userId,
    required bool checked,
  }) =>
      (_db.update(_db.shoppingListItems)
            ..where((t) => t.id.isIn(ids) & t.userId.equals(userId)))
          .write(ShoppingListItemsCompanion(isChecked: Value(checked)));

  Future<void> toggleItem({
    required int id,
    required String userId,
    required bool checked,
  }) {
    return (_db.update(_db.shoppingListItems)
          ..where((t) => t.id.equals(id) & t.userId.equals(userId)))
        .write(ShoppingListItemsCompanion(isChecked: Value(checked)));
  }

  Future<void> deleteItem({required int id, required String userId}) {
    return (_db.delete(
      _db.shoppingListItems,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).go();
  }

  /// Completes a checkout backed by a scanned receipt: removes only the
  /// checked rows whose ingredient the receipt actually resolved
  /// (AC-SHOP-01/AC-TEST-06), leaving every other row — checked-but-
  /// unmatched or never-checked — exactly as it was.
  ///
  /// Also this file's satisfaction of AC-SHOP-04 (R-03): `userId` +
  /// `isChecked` + a matched `ingredientId` is the same scoping a standalone
  /// "check off by ingredient" step would need, and doing it here — in the
  /// one statement that both matches *and* removes — means there's no
  /// separate tick step whose own scoping could be gotten wrong or skipped.
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

  /// Completes a receipt-less trip ("Done shopping", AC-SHOP-02): there is
  /// no receipt to partially match against, so every checked row is
  /// considered bought and removed.
  Future<int> completeCheckoutWithoutReceipt({required String userId}) {
    return (_db.delete(
      _db.shoppingListItems,
    )..where((t) => t.userId.equals(userId) & t.isChecked.equals(true))).go();
  }
}

class AiShoppingItem {
  const AiShoppingItem({
    required this.name,
    required this.quantity,
    required this.unit,
    this.apiIngredientId,
    this.category,
  });

  final String name;
  final double quantity;
  final String unit;
  final String? apiIngredientId;
  final String? category;
}
