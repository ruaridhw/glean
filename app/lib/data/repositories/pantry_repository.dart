// Ported from `mobile/src/db/pantry.ts`, with the schema changes from
// FLUTTER_MIGRATION.md §3/§6: every query is scoped by `userId`
// (AC-DATA-02/03), and `addItem` infers an expiry date from the ingredient's
// category shelf life (AC-PAN-01) — RN's `addPantryItem` never accepted or
// wrote one at all.
import 'package:drift/drift.dart';

import '../database.dart';
import '../models/pantry_item_view.dart';
import '../util/unit_normalization.dart';
import '../util/week.dart';
import 'ingredients_repository.dart';

/// One accepted row from the review screen, ready to commit
/// (`addItems`/AC-PAN-10).
class PantryItemInput {
  const PantryItemInput({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.category,
    this.unitPrice,
  });

  final String name;
  final double quantity;
  final String unit;
  final String category;
  final double? unitPrice;
}

/// What was actually removed from a pantry row for one ingredient during
/// "Cooked" — the exact figures `PlanRepository` needs to record in
/// `cooked_adjustments` so undo can restore them precisely (AC-UX-03).
class PantryCookDelta {
  const PantryCookDelta({
    required this.unit,
    required this.amountApplied,
    required this.previousLastUsedAt,
  });

  final String unit;
  final double amountApplied;
  final String? previousLastUsedAt;
}

class PantryRepository {
  PantryRepository(this._db, this._ingredients);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;

  /// All of [userId]'s pantry items, ordered like the RN app: soonest
  /// expiry first, then longest-unused first within the same expiry bucket.
  /// Inner-joins through `ingredients.category` to `ingredient_categories`,
  /// so `foodGroup` on the result is structurally non-null (AC-DATA-11) —
  /// there is no row to read if that join fails to match.
  Stream<List<PantryItemView>> watchAll(String userId) {
    final query =
        _db.select(_db.pantryItems).join([
            innerJoin(
              _db.ingredients,
              _db.ingredients.id.equalsExp(_db.pantryItems.ingredientId),
            ),
            innerJoin(
              _db.ingredientCategories,
              _db.ingredientCategories.category.equalsExp(
                _db.ingredients.category,
              ),
            ),
          ])
          ..where(_db.pantryItems.userId.equals(userId))
          ..orderBy([
            OrderingTerm(
              expression: coalesce([
                _db.pantryItems.expiryDate,
                const Constant('9999-12-31'),
              ]),
            ),
            OrderingTerm(
              expression: coalesce([
                _db.pantryItems.lastUsedAt,
                const Constant('0000-01-01'),
              ]),
            ),
          ]);
    return query.watch().map((rows) => rows.map(_mapRow).toList());
  }

  PantryItemView _mapRow(TypedResult row) {
    final item = row.readTable(_db.pantryItems);
    final ingredient = row.readTable(_db.ingredients);
    final category = row.readTable(_db.ingredientCategories);
    return PantryItemView(
      id: item.id,
      userId: item.userId,
      ingredientId: item.ingredientId,
      quantity: item.quantity,
      unit: item.unit,
      unitPrice: item.unitPrice,
      expiryDate: item.expiryDate == null ? null : parseDate(item.expiryDate!),
      lastUsedAt: item.lastUsedAt == null
          ? null
          : DateTime.parse(item.lastUsedAt!),
      updatedAt: DateTime.parse(item.updatedAt),
      canonicalName: ingredient.canonicalName,
      isStaple: ingredient.isStaple,
      category: category.category,
      foodGroup: category.foodGroup,
      shelfLifeDays: category.shelfLifeDays,
    );
  }

  /// Resolves (or creates) the ingredient for [name], normalizes the
  /// quantity/unit against its canonical unit, infers an expiry date from
  /// the category's shelf life, and upserts the pantry row — the single
  /// entry point for adding to the pantry, mirroring RN's `addPantryItem`
  /// but with a required [category] (see `IngredientsRepository`) and real
  /// expiry inference. Top-up (an existing row for the same ingredient)
  /// adds to the existing quantity and refreshes the expiry, since the
  /// freshly-added stock is what's now on the shelf.
  Future<int> addItem({
    required String userId,
    required String name,
    required double quantity,
    required String unit,
    required String category,
    double? unitPrice,
    DateTime? now,
  }) async {
    final effectiveNow = now ?? DateTime.now();
    final ingredient = await _ingredients.resolveOrCreate(
      canonicalName: name,
      category: category,
    );
    final normalized = normalizeUnit(
      quantity: quantity,
      unit: unit,
      canonicalUnit: ingredient.canonicalUnit,
      canonicalName: ingredient.canonicalName,
    );
    final shelfLifeDays = await _shelfLifeDaysFor(ingredient.category!);
    final expiry = effectiveNow.add(Duration(days: shelfLifeDays));

    await _upsert(
      userId: userId,
      ingredientId: ingredient.id,
      quantity: normalized?.quantity ?? quantity,
      unit: normalized?.unit ?? unit,
      unitPrice: unitPrice,
      expiryDate: expiry,
      now: effectiveNow,
    );
    return ingredient.id;
  }

  /// Commits every accepted row from a review screen as a single
  /// transaction (AC-PAN-10): a failure partway through persists nothing —
  /// unlike RN's review-confirm loop, which called `addPantryItem` per row
  /// with no transaction, so a failure on row 3 of 5 left rows 1-2 already
  /// incremented, and retrying the whole list doubled them. Here, a failed
  /// attempt leaves nothing committed, so retrying starts from the same
  /// clean slate and cannot double anything.
  Future<List<int>> addItems({
    required String userId,
    required List<PantryItemInput> items,
    DateTime? now,
  }) {
    return _db.transaction(() async {
      final ids = <int>[];
      for (final item in items) {
        ids.add(
          await addItem(
            userId: userId,
            name: item.name,
            quantity: item.quantity,
            unit: item.unit,
            category: item.category,
            unitPrice: item.unitPrice,
            now: now,
          ),
        );
      }
      return ids;
    });
  }

  Future<int> _shelfLifeDaysFor(String category) async {
    final row = await (_db.select(
      _db.ingredientCategories,
    )..where((t) => t.category.equals(category))).getSingle();
    return row.shelfLifeDays;
  }

  Future<void> _upsert({
    required String userId,
    required int ingredientId,
    required double quantity,
    required String unit,
    double? unitPrice,
    required DateTime expiryDate,
    required DateTime now,
  }) async {
    final existing =
        await (_db.select(_db.pantryItems)..where(
              (t) =>
                  t.userId.equals(userId) & t.ingredientId.equals(ingredientId),
            ))
            .getSingleOrNull();

    if (existing != null) {
      await (_db.update(
        _db.pantryItems,
      )..where((t) => t.id.equals(existing.id))).write(
        PantryItemsCompanion(
          quantity: Value(existing.quantity + quantity),
          unitPrice: unitPrice != null
              ? Value(unitPrice)
              : const Value.absent(),
          expiryDate: Value(formatDate(expiryDate)),
          updatedAt: Value(now.toIso8601String()),
        ),
      );
    } else {
      await _db
          .into(_db.pantryItems)
          .insert(
            PantryItemsCompanion.insert(
              userId: userId,
              ingredientId: ingredientId,
              quantity: quantity,
              unit: unit,
              unitPrice: Value(unitPrice),
              expiryDate: Value(formatDate(expiryDate)),
              updatedAt: now.toIso8601String(),
            ),
          );
    }
  }

  /// Backs the quantity/unit/expiry edit sheet (AC-PAN-07) — every field is
  /// optional so the sheet can save just what changed.
  Future<void> updateItem({
    required int id,
    required String userId,
    double? quantity,
    String? unit,
    DateTime? expiryDate,
    DateTime? now,
  }) {
    return (_db.update(
      _db.pantryItems,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).write(
      PantryItemsCompanion(
        quantity: quantity != null ? Value(quantity) : const Value.absent(),
        unit: unit != null ? Value(unit) : const Value.absent(),
        expiryDate: expiryDate != null
            ? Value(formatDate(expiryDate))
            : const Value.absent(),
        updatedAt: Value((now ?? DateTime.now()).toIso8601String()),
      ),
    );
  }

  Future<void> deleteItem({required int id, required String userId}) {
    return (_db.delete(
      _db.pantryItems,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).go();
  }

  /// Decrements the pantry row for [ingredientId], floored at zero, as part
  /// of marking a meal "Cooked". Returns the amount actually removed (which
  /// may be less than [amount] if the pantry held less than that) and the
  /// row's previous `lastUsedAt` — both are what `PlanRepository` needs to
  /// reverse this exactly later. Returns null if there is no pantry row for
  /// this ingredient (nothing to decrement, nothing to undo).
  Future<PantryCookDelta?> decrementForCook({
    required String userId,
    required int ingredientId,
    required double amount,
    required DateTime now,
  }) async {
    final row =
        await (_db.select(_db.pantryItems)..where(
              (t) =>
                  t.userId.equals(userId) & t.ingredientId.equals(ingredientId),
            ))
            .getSingleOrNull();
    if (row == null) return null;

    final applied = amount > row.quantity ? row.quantity : amount;
    await (_db.update(
      _db.pantryItems,
    )..where((t) => t.id.equals(row.id))).write(
      PantryItemsCompanion(
        quantity: Value(row.quantity - applied),
        lastUsedAt: Value(now.toIso8601String()),
        updatedAt: Value(now.toIso8601String()),
      ),
    );
    return PantryCookDelta(
      unit: row.unit,
      amountApplied: applied,
      previousLastUsedAt: row.lastUsedAt,
    );
  }

  /// Reverses [decrementForCook] exactly: restores the applied quantity and
  /// the prior `lastUsedAt`. If the user deleted the pantry row after
  /// cooking, recreates it best-effort (there is no prior expiry to
  /// restore in that case).
  Future<void> restoreFromCook({
    required String userId,
    required int ingredientId,
    required double amount,
    required String unit,
    required String? previousLastUsedAt,
    required DateTime now,
  }) async {
    final row =
        await (_db.select(_db.pantryItems)..where(
              (t) =>
                  t.userId.equals(userId) & t.ingredientId.equals(ingredientId),
            ))
            .getSingleOrNull();

    if (row == null) {
      await _db
          .into(_db.pantryItems)
          .insert(
            PantryItemsCompanion.insert(
              userId: userId,
              ingredientId: ingredientId,
              quantity: amount,
              unit: unit,
              lastUsedAt: Value(previousLastUsedAt),
              updatedAt: now.toIso8601String(),
            ),
          );
      return;
    }

    await (_db.update(
      _db.pantryItems,
    )..where((t) => t.id.equals(row.id))).write(
      PantryItemsCompanion(
        quantity: Value(row.quantity + amount),
        lastUsedAt: Value(previousLastUsedAt),
        updatedAt: Value(now.toIso8601String()),
      ),
    );
  }
}
