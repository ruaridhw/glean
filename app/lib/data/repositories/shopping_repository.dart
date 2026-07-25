// Ported from the Expo app's `src/db/shopping.ts` (see git history),
// fixing the three data-integrity bugs FLUTTER_MIGRATION.md §11/§6 Shop
// call out:
//
//   - `resolveCheckout` (AC-SHOP-01) replaces `completeCheckout`, which
//     deleted *every* checked row regardless of receipt match — check off
//     12 items, scan a receipt matching 4, and the other 8 vanished without
//     ever becoming pantry stock. This version deletes only rows whose
//     ingredient the receipt actually resolved, in one statement, so there
//     is no window where an unmatched checked row could be swept up.
//   - `checkOffResolvedIngredients` (AC-SHOP-04) replaces
//     `checkOffByIngredientIds`, which had no user scope at all and
//     unconditionally flipped every row sharing an ingredient id. This
//     version is scoped to the current user and only ever moves a row from
//     unchecked -> checked — it can't re-affect an already-checked row or
//     touch another user's list.
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

class ShoppingRepository {
  ShoppingRepository(this._db, this._ingredients);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;

  Stream<List<ShoppingListItemView>> watchAll(String userId) {
    final query = _db.select(_db.shoppingListItems)
      ..where((t) => t.userId.equals(userId))
      ..orderBy([
        (t) => OrderingTerm.asc(t.isChecked),
        (t) => OrderingTerm.desc(t.id),
      ]);
    return query.watch().map((rows) => rows.map(_mapRow).toList());
  }

  ShoppingListItemView _mapRow(ShoppingListItem row) => ShoppingListItemView(
    id: row.id,
    userId: row.userId,
    ingredientId: row.ingredientId,
    name: row.name,
    quantity: row.quantity,
    unit: row.unit,
    source: row.source,
    isChecked: row.isChecked,
    sourceMealPlanEntryId: row.sourceMealPlanEntryId,
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
  /// from its parsed unit for the same reason. Runs as a single transaction
  /// (AC-PAN-10): a failure partway through the list persists nothing, so
  /// retrying can't double-insert the rows that already succeeded.
  Future<void> addAiItems({
    required String userId,
    required List<AiShoppingItem> items,
  }) {
    return _db.transaction(() async {
      for (final item in items) {
        final name = item.name.trim();
        if (name.isEmpty) continue;
        final unit = item.unit.trim().isEmpty ? 'units' : item.unit.trim();
        final ingredient = await _ingredients.resolveOrCreate(
          canonicalName: name,
          apiIngredientId: item.apiIngredientId,
          category: item.category,
          unit: unit,
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

  /// Adds a shopping row for each non-optional ingredient of [recipeId]
  /// that the pantry can't fully cover for [servings], linked back to
  /// [sourceMealPlanEntryId] so deleting that plan entry removes this row
  /// too (AC-SHOP-06).
  Future<void> addGapsForRecipe({
    required String userId,
    required int recipeId,
    required int servings,
    required int sourceMealPlanEntryId,
  }) async {
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
      final needed = recipeIngredient.quantity * servings;

      final pantryRow =
          await (_db.select(_db.pantryItems)..where(
                (t) =>
                    t.userId.equals(userId) &
                    t.ingredientId.equals(recipeIngredient.ingredientId),
              ))
              .getSingleOrNull();
      final available = pantryRow?.quantity ?? 0;
      if (available >= needed) continue;
      final shortfall = needed - available;

      final existing =
          await (_db.select(_db.shoppingListItems)..where(
                (t) =>
                    t.userId.equals(userId) &
                    t.ingredientId.equals(recipeIngredient.ingredientId) &
                    t.isChecked.equals(false),
              ))
              .getSingleOrNull();
      if (existing != null) continue;

      await _db
          .into(_db.shoppingListItems)
          .insert(
            ShoppingListItemsCompanion.insert(
              userId: userId,
              ingredientId: recipeIngredient.ingredientId,
              name: ingredient.canonicalName,
              quantity: Value(shortfall),
              unit: Value(recipeIngredient.unit),
              source: const Value('meal_plan'),
              sourceMealPlanEntryId: Value(sourceMealPlanEntryId),
            ),
          );
    }
  }

  /// Flips unchecked rows matching [ingredientIds] to checked, for
  /// [userId] only. Never touches an already-checked row (so it can't
  /// interfere with a checkout in progress) and never touches another
  /// user's list — the scoping RN's `checkOffByIngredientIds` lacked
  /// entirely (AC-SHOP-04).
  Future<void> checkOffResolvedIngredients({
    required String userId,
    required List<int> ingredientIds,
  }) {
    if (ingredientIds.isEmpty) return Future.value();
    return (_db.update(_db.shoppingListItems)..where(
          (t) =>
              t.userId.equals(userId) &
              t.ingredientId.isIn(ingredientIds) &
              t.isChecked.equals(false),
        ))
        .write(const ShoppingListItemsCompanion(isChecked: Value(true)));
  }

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
