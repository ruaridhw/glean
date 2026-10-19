// Pantry persistence. Every query is scoped by `userId`, and `addItem` infers an expiry date from the
// ingredient's shelf life.
import 'package:drift/drift.dart';

import '../database.dart';
import '../models/pantry_item_view.dart';
import '../util/shelf_life.dart';
import '../util/unit_normalization.dart';
import '../util/week.dart';
import 'catalogue_repository.dart';
import 'ingredients_repository.dart';

/// One accepted row from the review screen, ready to commit via `addItems`.
class PantryItemInput {
  const PantryItemInput({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.groupId,
    this.unitPrice,
  });

  final String name;
  final double quantity;
  final String unit;

  /// Null stores the Pantry item unclassified (food group "other") with no inferred expiry.
  final String? groupId;
  final double? unitPrice;
}

/// What one checkout did to the Pantry item of one ingredient: the row as it stood before (null when the
/// checkout created it) and the quantity the checkout added, so Undo can take back exactly that.
class PantryAddition {
  const PantryAddition({
    required this.ingredientId,
    required this.previous,
    required this.quantityAdded,
  });

  final int ingredientId;
  final PantryItem? previous;
  final double quantityAdded;
}

/// Short-lived Undo receipt for [PantryRepository.addItemsWithReceipt].
class PantryAdditionReceipt {
  PantryAdditionReceipt(List<PantryAddition> additions)
    : additions = List.unmodifiable(additions);

  final List<PantryAddition> additions;
}

/// What was actually removed from a pantry row for one ingredient during "Cooked", so `PlanRepository` can
/// record it in `cooked_adjustments` and undo can restore it precisely.
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

/// Thrown by [PantryRepository.addItem] (via `_upsert`) when an add would merge into an existing row under a
/// unit no conversion path connects to that row's unit (e.g. 'g' stock added to in 'units'). Summing would
/// silently corrupt the quantity, so it fails loudly.
///
/// Callers must show [userMessage], not a generic "try again": retrying the same unit fails identically. The
/// only way out is entering the quantity in [existingUnit] (or editing the existing row's unit).
class PantryUnitMismatchException implements Exception {
  const PantryUnitMismatchException({
    required this.ingredientId,
    required this.canonicalName,
    required this.existingUnit,
    required this.incomingUnit,
  });

  final int ingredientId;
  final String canonicalName;
  final String existingUnit;
  final String incomingUnit;

  /// What to show the user: names the ingredient, both units, and the one
  /// thing that actually fixes it — never "try again".
  String get userMessage =>
      '$canonicalName is stocked in $existingUnit — enter this amount in '
      '$existingUnit instead of $incomingUnit.';

  @override
  String toString() =>
      'PantryUnitMismatchException: cannot merge $incomingUnit into the '
      'existing pantry row for ingredient $ingredientId ($canonicalName), '
      'stocked in $existingUnit — no conversion path exists between them.';
}

class PantryRepository {
  PantryRepository(this._db, this._ingredients)
    : _catalogue = CatalogueRepository(_db);

  final GleanDatabase _db;
  final IngredientsRepository _ingredients;
  final CatalogueRepository _catalogue;

  /// All of [userId]'s pantry items, soonest expiry first, then longest-unused first within the same expiry.
  ///
  /// `ingredients` is inner-joined (the FK is NOT NULL), but `ingredient_groups` is left-joined because
  /// `ingredients.group_id` is nullable: an unclassified ingredient must still surface its pantry row. `_mapRow`
  /// coalesces the missing food group to `"other"`, matching the backend.
  Stream<List<PantryItemView>> watchAll(String userId) =>
      _itemsQuery(userId).watch().asyncMap(_mapRows);

  /// One-shot twin of [watchAll]: same query, a plain `.get()` rather than a
  /// subscription opened and immediately cancelled.
  Future<List<PantryItemView>> getAll(String userId) async =>
      _mapRows(await _itemsQuery(userId).get());

  JoinedSelectStatement<HasResultSet, dynamic> _itemsQuery(String userId) =>
      _db.select(_db.pantryItems).join([
          innerJoin(
            _db.ingredients,
            _db.ingredients.id.equalsExp(_db.pantryItems.ingredientId),
          ),
          leftOuterJoin(
            _db.ingredientGroups,
            _db.ingredientGroups.id.equalsExp(_db.ingredients.groupId),
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

  Future<List<PantryItemView>> _mapRows(List<TypedResult> rows) async => [
    for (final row in rows) await _mapRow(row),
  ];

  // Fallback for a pantry item whose ingredient has no group; matches the backend's "other" bucket.
  static const String _unclassifiedFoodGroup = 'other';

  Future<PantryItemView> _mapRow(TypedResult row) async {
    final item = row.readTable(_db.pantryItems);
    final ingredient = row.readTable(_db.ingredients);
    final group = row.readTableOrNull(_db.ingredientGroups);
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
      groupId: ingredient.groupId,
      foodGroup: group?.foodGroup ?? _unclassifiedFoodGroup,
      shelfLifeDays: await _shelfLifeDays(ingredient, group),
    );
  }

  /// The ingredient's unopened shelf life in days, null when it has none to infer. A linked ingredient asks the
  /// catalogue's resolver, so the household's own shelf lives count; an unlinked one takes its group's.
  Future<int?> _shelfLifeDays(
    Ingredient ingredient,
    IngredientGroup? group,
  ) async {
    final itemId = ingredient.catalogueItemId;
    if (itemId != null) {
      final effective = await _catalogue.effectiveIngredient(itemId);
      if (effective != null) return effective.unopenedShelfLifeDays;
    }
    return unlinkedShelfLifeDays(group, ingredient.form);
  }

  /// Resolves (or creates) the ingredient for [name], normalizes quantity/unit against its canonical unit,
  /// infers an expiry from the ingredient's shelf life, and upserts the pantry row. A top-up adds to the existing
  /// quantity and refreshes the expiry, since the new stock is what's now on the shelf.
  Future<int> addItem({
    required String userId,
    required String name,
    required double quantity,
    required String unit,
    required String? groupId,
    double? unitPrice,
    DateTime? now,
  }) async {
    final effectiveNow = now ?? DateTime.now();
    // A blank `unit` still needs some string for the row and `normalizeUnit`, so it defaults to `'units'`, but
    // that fallback must never reach `resolveOrCreate`'s seeding parameter: it would become the ingredient's
    // permanent canonical unit.
    final String trimmedUnit = unit.trim();
    final String effectiveUnit = trimmedUnit.isEmpty ? 'units' : trimmedUnit;
    final ingredient = await _ingredients.resolveOrCreate(
      canonicalName: name,
      groupId: groupId,
      unit: trimmedUnit.isEmpty ? null : trimmedUnit,
    );
    final normalized = normalizeUnit(
      quantity: quantity,
      unit: effectiveUnit,
      canonicalUnit: ingredient.canonicalUnit,
      canonicalName: ingredient.canonicalName,
    );
    // An ingredient with no shelf life to infer (unclassified, or one that never expires) gets no expiry.
    final int? shelfLifeDays = await _shelfLifeDays(
      ingredient,
      await _groupOf(ingredient),
    );
    final DateTime? expiry = shelfLifeDays == null
        ? null
        : addDays(effectiveNow, shelfLifeDays);

    await _upsert(
      userId: userId,
      ingredientId: ingredient.id,
      canonicalName: ingredient.canonicalName,
      quantity: normalized?.quantity ?? quantity,
      unit: normalized?.unit ?? effectiveUnit,
      unitPrice: unitPrice,
      expiryDate: expiry,
      now: effectiveNow,
    );
    return ingredient.id;
  }

  /// Commits every accepted row from a review screen as a single transaction: a failure partway persists
  /// nothing, so retrying cannot double anything.
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
            groupId: item.groupId,
            unitPrice: item.unitPrice,
            now: now,
          ),
        );
      }
      return ids;
    });
  }

  /// [addItems], plus a receipt of what each touched Pantry item looked like before and how much was added to
  /// it, for [undoAdditions].
  Future<PantryAdditionReceipt> addItemsWithReceipt({
    required String userId,
    required List<PantryItemInput> items,
    DateTime? now,
  }) {
    return _db.transaction(() async {
      final before = {
        for (final row in await (_db.select(
          _db.pantryItems,
        )..where((t) => t.userId.equals(userId))).get())
          row.ingredientId: row,
      };
      final ids = await addItems(userId: userId, items: items, now: now);
      final additions = <PantryAddition>[];
      for (final id in ids.toSet()) {
        final after =
            await (_db.select(_db.pantryItems)..where(
                  (t) => t.userId.equals(userId) & t.ingredientId.equals(id),
                ))
                .getSingle();
        additions.add(
          PantryAddition(
            ingredientId: id,
            previous: before[id],
            quantityAdded: after.quantity - (before[id]?.quantity ?? 0),
          ),
        );
      }
      return PantryAdditionReceipt(additions);
    });
  }

  /// Reverses [addItemsWithReceipt]: deletes the Pantry items it created and subtracts exactly the added
  /// quantity (and restores the expiry and price the merge overwrote) on the ones that already existed.
  Future<void> undoAdditions({
    required String userId,
    required PantryAdditionReceipt receipt,
    DateTime? now,
  }) {
    return _db.transaction(() async {
      for (final addition in receipt.additions) {
        final row =
            await (_db.select(_db.pantryItems)..where(
                  (t) =>
                      t.userId.equals(userId) &
                      t.ingredientId.equals(addition.ingredientId),
                ))
                .getSingleOrNull();
        if (row == null) continue;
        final previous = addition.previous;
        if (previous == null) {
          await (_db.delete(
            _db.pantryItems,
          )..where((t) => t.id.equals(row.id))).go();
        } else {
          await (_db.update(
            _db.pantryItems,
          )..where((t) => t.id.equals(row.id))).write(
            PantryItemsCompanion(
              quantity: Value(row.quantity - addition.quantityAdded),
              unitPrice: Value(previous.unitPrice),
              expiryDate: Value(previous.expiryDate),
              updatedAt: Value((now ?? DateTime.now()).toIso8601String()),
            ),
          );
        }
      }
    });
  }

  Future<IngredientGroup?> _groupOf(Ingredient ingredient) {
    final groupId = ingredient.groupId;
    if (groupId == null) return Future.value();
    return (_db.select(
      _db.ingredientGroups,
    )..where((t) => t.id.equals(groupId))).getSingleOrNull();
  }

  /// [canonicalName] is only needed for the density fallback in the
  /// mismatch-reconciliation path below — it plays no part when [unit]
  /// already matches the existing row.
  Future<void> _upsert({
    required String userId,
    required int ingredientId,
    required String canonicalName,
    required double quantity,
    required String unit,
    double? unitPrice,
    required DateTime? expiryDate,
    required DateTime now,
  }) async {
    final existing =
        await (_db.select(_db.pantryItems)..where(
              (t) =>
                  t.userId.equals(userId) & t.ingredientId.equals(ingredientId),
            ))
            .getSingleOrNull();

    if (existing != null) {
      // `unit` should already be normalized into `canonicalUnit` by `addItem`. This is the last line of defence
      // against mixed-unit sums (e.g. a row that predates `canonicalUnit`, or no conversion path): re-normalize
      // against this row's own unit, the ground truth of what's on the shelf, before merging.
      final normalizedUnit = unit.toLowerCase().trim();
      double mergeQuantity = quantity;
      if (normalizedUnit != existing.unit) {
        final reconciled = normalizeUnit(
          quantity: quantity,
          unit: unit,
          canonicalUnit: existing.unit,
          canonicalName: canonicalName,
        );
        if (reconciled == null) {
          throw PantryUnitMismatchException(
            ingredientId: ingredientId,
            canonicalName: canonicalName,
            existingUnit: existing.unit,
            incomingUnit: unit,
          );
        }
        mergeQuantity = reconciled.quantity;
      }

      await (_db.update(
        _db.pantryItems,
      )..where((t) => t.id.equals(existing.id))).write(
        PantryItemsCompanion(
          quantity: Value(existing.quantity + mergeQuantity),
          unitPrice: unitPrice != null
              ? Value(unitPrice)
              : const Value.absent(),
          expiryDate: Value(expiryDate == null ? null : formatDate(expiryDate)),
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
              expiryDate: Value(
                expiryDate == null ? null : formatDate(expiryDate),
              ),
              updatedAt: now.toIso8601String(),
            ),
          );
    }
  }

  /// Every field is optional so the edit sheet can save just what changed.
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

  /// Restores deleted stock without treating it as a fresh purchase. If new
  /// stock was added meanwhile, merge quantity but retain that row's metadata.
  Future<void> restoreDeletedItem({
    required String userId,
    required PantryItemView item,
  }) {
    if (item.userId != userId) {
      throw StateError('Cannot restore another user\'s stock');
    }
    return _db.transaction(() async {
      final existing =
          await (_db.select(_db.pantryItems)..where(
                (t) =>
                    t.userId.equals(userId) &
                    t.ingredientId.equals(item.ingredientId),
              ))
              .getSingleOrNull();
      final now = DateTime.now();
      if (existing != null) {
        await _upsert(
          userId: userId,
          ingredientId: item.ingredientId,
          canonicalName: item.canonicalName,
          quantity: item.quantity,
          unit: item.unit,
          unitPrice: existing.unitPrice,
          expiryDate: existing.expiryDate == null
              ? null
              : DateTime.parse(existing.expiryDate!),
          now: now,
        );
        return;
      }
      await _db
          .into(_db.pantryItems)
          .insert(
            PantryItemsCompanion.insert(
              id: Value(item.id),
              userId: userId,
              ingredientId: item.ingredientId,
              quantity: item.quantity,
              unit: item.unit,
              unitPrice: Value(item.unitPrice),
              expiryDate: Value(
                item.expiryDate == null ? null : formatDate(item.expiryDate!),
              ),
              lastUsedAt: Value(item.lastUsedAt?.toIso8601String()),
              updatedAt: now.toIso8601String(),
            ),
          );
    });
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

  /// Reverses [decrementForCook] exactly: restores the applied quantity always, and the prior `lastUsedAt`
  /// only when [restoreLastUsedAt] is true. If the user deleted the pantry row after cooking, recreates it
  /// best-effort (there is no prior expiry to restore).
  ///
  /// Quantity is additive and safe to always restore, but `lastUsedAt` is last-writer-wins:
  /// `PlanRepository.undoCooked` passes [restoreLastUsedAt] explicitly so undoing an earlier cook while a later
  /// one stands doesn't overwrite the later timestamp. Defaults to `true` for direct callers with nothing to clobber.
  Future<void> restoreFromCook({
    required String userId,
    required int ingredientId,
    required double amount,
    required String unit,
    required String? previousLastUsedAt,
    required DateTime now,
    bool restoreLastUsedAt = true,
  }) async {
    final row =
        await (_db.select(_db.pantryItems)..where(
              (t) =>
                  t.userId.equals(userId) & t.ingredientId.equals(ingredientId),
            ))
            .getSingleOrNull();

    if (row == null) {
      // Nothing exists to "leave alone" — there is no current value, only
      // the snapshot this adjustment carries — so restore it regardless of
      // [restoreLastUsedAt].
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
        lastUsedAt: restoreLastUsedAt
            ? Value(previousLastUsedAt)
            : const Value.absent(),
        updatedAt: Value(now.toIso8601String()),
      ),
    );
  }
}
