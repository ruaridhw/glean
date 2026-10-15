// Ported from the Expo app's `src/db/plan.ts` (see git history), with the
// schema changes
// FLUTTER_MIGRATION.md §6 Plan requires:
//
//   - Week-scoped reads and a per-week capacity (AC-PLAN-01/04) in place of
//     RN's unfiltered `getMealPlanEntries` and lifetime `getMealPlanCount`,
//     which eventually blocked every add permanently.
//   - `servings` has no default anywhere in this file — every call to
//     `addEntry` must state it explicitly, so `preferred_servings` can't be
//     silently re-hardcoded to 1 the way RN's `addMealPlanEntry` did
//     (AC-PLAN-07).
//   - Idempotent rollover (AC-PLAN-05): uncooked meals move forward into the
//     current week by *updating* `plannedDate` rather than inserting a
//     duplicate row, so running it twice is a no-op the second time.
//   - Undoable "Cooked" (AC-UX-03): `markCooked`/`undoCooked` record and
//     reverse the exact pantry delta via `cooked_adjustments`.
import 'package:drift/drift.dart';

import '../database.dart';
import '../deletion_snapshots.dart';
import '../models/meal_plan_entry_view.dart';
import '../util/recipe_servings.dart';
import '../util/unit_normalization.dart';
import '../util/week.dart';
import 'pantry_repository.dart';

class PlanRepository {
  PlanRepository(this._db, this._pantry);

  final GleanDatabase _db;
  final PantryRepository _pantry;

  /// Entries whose `plannedDate` falls within the week starting
  /// [weekStart] (a Monday — see `startOfWeek`), ordered by date then
  /// insertion order. Cooked entries are included (they stay visible in
  /// their week, AC-PLAN-03) — callers exclude them from "left to plan"
  /// counts using [MealPlanEntryView.isCooked].
  Stream<List<MealPlanEntryView>> watchWeek({
    required String userId,
    required DateTime weekStart,
  }) {
    final start = formatDate(weekStart);
    final end = formatDate(endOfWeek(weekStart));
    final query = _db.select(_db.mealPlanEntries)
      ..where(
        (t) =>
            t.userId.equals(userId) &
            t.plannedDate.isBiggerOrEqualValue(start) &
            t.plannedDate.isSmallerThanValue(end),
      )
      ..orderBy([
        (t) => OrderingTerm.asc(t.plannedDate),
        (t) => OrderingTerm.asc(t.id),
      ]);
    return query.watch().map((rows) => rows.map(_mapEntry).toList());
  }

  /// One-shot twin of [watchWeek]: same week window and ordering, but a
  /// plain `.get()`. Command paths (e.g. meal-plan generation) need a
  /// snapshot of this week's entries, not a subscription opened and
  /// immediately cancelled (FINDINGS.md F-14).
  Future<List<MealPlanEntryView>> getWeek({
    required String userId,
    required DateTime weekStart,
  }) async {
    final start = formatDate(weekStart);
    final end = formatDate(endOfWeek(weekStart));
    final query = _db.select(_db.mealPlanEntries)
      ..where(
        (t) =>
            t.userId.equals(userId) &
            t.plannedDate.isBiggerOrEqualValue(start) &
            t.plannedDate.isSmallerThanValue(end),
      )
      ..orderBy([
        (t) => OrderingTerm.asc(t.plannedDate),
        (t) => OrderingTerm.asc(t.id),
      ]);
    final rows = await query.get();
    return rows.map(_mapEntry).toList();
  }

  MealPlanEntryView _mapEntry(MealPlanEntry row) => MealPlanEntryView(
    id: row.id,
    userId: row.userId,
    recipeId: row.recipeId,
    recipeTitle: row.recipeTitle,
    plannedDate: parseDate(row.plannedDate),
    cookedAt: row.cookedAt == null ? null : DateTime.parse(row.cookedAt!),
    servings: row.servings,
    externalIdSnapshot: row.externalIdSnapshot,
  );

  /// Uncooked entries in the week starting [weekStart] — the figure "left
  /// to plan" and per-week capacity are both based on (AC-PLAN-03/04):
  /// cooked meals stay visible but free up their slot.
  Future<int> uncookedCountForWeek({
    required String userId,
    required DateTime weekStart,
  }) async {
    final start = formatDate(weekStart);
    final end = formatDate(endOfWeek(weekStart));
    final countExpression = _db.mealPlanEntries.id.count();
    final query = _db.selectOnly(_db.mealPlanEntries)
      ..addColumns([countExpression])
      ..where(
        _db.mealPlanEntries.userId.equals(userId) &
            _db.mealPlanEntries.cookedAt.isNull() &
            _db.mealPlanEntries.plannedDate.isBiggerOrEqualValue(start) &
            _db.mealPlanEntries.plannedDate.isSmallerThanValue(end),
      );
    final row = await query.getSingle();
    return row.read(countExpression) ?? 0;
  }

  /// How many more meals can be added to the week starting [weekStart],
  /// derived from the user's `mealsPerWeek` setting minus the uncooked
  /// count for that week — never negative. Per-week, not lifetime
  /// (AC-PLAN-04): a fully-booked week from a month ago has no bearing on
  /// this week's capacity.
  Future<int> remainingCapacityForWeek({
    required String userId,
    required DateTime weekStart,
  }) async {
    final config = await (_db.select(
      _db.userConfig,
    )..where((t) => t.id.equals(userId))).getSingleOrNull();
    final mealsPerWeek = config?.mealsPerWeek ?? 5;
    final uncooked = await uncookedCountForWeek(
      userId: userId,
      weekStart: weekStart,
    );
    final remaining = mealsPerWeek - uncooked;
    return remaining > 0 ? remaining : 0;
  }

  Future<int> addEntry({
    required String userId,
    required int recipeId,
    required String recipeTitle,
    required int servings,
    DateTime? plannedDate,
  }) async {
    final recipe =
        await (_db.select(_db.recipes)
              ..where((t) => t.id.equals(recipeId) & t.userId.equals(userId)))
            .getSingle();
    return _db
        .into(_db.mealPlanEntries)
        .insert(
          MealPlanEntriesCompanion.insert(
            userId: userId,
            recipeId: Value(recipeId),
            recipeTitle: recipeTitle,
            plannedDate: formatDate(plannedDate ?? DateTime.now()),
            servings: servings,
            externalIdSnapshot: Value(recipe.externalId),
          ),
        );
  }

  /// Deletes the entry. Its plan-derived shopping rows cascade away with it
  /// (AC-SHOP-06) via `shopping_list_items.sourceMealPlanEntryId`'s
  /// `onDelete: cascade` — no manual sweep needed here.
  Future<DeletedPlanEntry> deleteWithSnapshot({
    required int id,
    required String userId,
  }) => _db.transaction(() async {
    final entry = await (_db.select(
      _db.mealPlanEntries,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).getSingle();
    final shopping =
        await (_db.select(_db.shoppingListItems)..where(
              (t) =>
                  t.sourceMealPlanEntryId.equals(id) & t.userId.equals(userId),
            ))
            .get();
    final adjustments =
        await (_db.select(_db.cookedAdjustments)..where(
              (t) => t.mealPlanEntryId.equals(id) & t.userId.equals(userId),
            ))
            .get();
    await deleteEntry(id: id, userId: userId);
    return DeletedPlanEntry(entry, shopping, adjustments);
  });

  Future<void> restoreDeleted({
    required DeletedPlanEntry snapshot,
    required String userId,
  }) => _db.transaction(() async {
    if (snapshot.entry.userId != userId) {
      throw ArgumentError('Undo belongs to another user');
    }
    final entry = snapshot.entry;
    if (entry.cookedAt == null &&
        await remainingCapacityForWeek(
              userId: userId,
              weekStart: startOfWeek(DateTime.parse(entry.plannedDate)),
            ) <=
            0) {
      throw StateError('Plan is full');
    }
    var companion = entry.toCompanion(false);
    if (entry.recipeId != null &&
        await (_db.select(_db.recipes)..where(
                  (t) => t.id.equals(entry.recipeId!) & t.userId.equals(userId),
                ))
                .getSingleOrNull() ==
            null) {
      companion = companion.copyWith(recipeId: const Value(null));
    }
    await _db.into(_db.mealPlanEntries).insert(companion);
    for (final row in snapshot.shopping) {
      await _db.into(_db.shoppingListItems).insert(row.toCompanion(false));
    }
    for (final row in snapshot.adjustments) {
      await _db.into(_db.cookedAdjustments).insert(row.toCompanion(false));
    }
  });

  Future<void> deleteEntry({required int id, required String userId}) {
    return (_db.delete(
      _db.mealPlanEntries,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).go();
  }

  /// Moves every uncooked entry still dated before the week starting
  /// [referenceDate] (default now) forward into that week, so nothing
  /// planned is lost when a week turns over. This *updates* `plannedDate`
  /// rather than inserting a new row, which is what makes it safe to call
  /// repeatedly (AC-PLAN-05): once an entry's date is inside the target
  /// week, this query no longer matches it.
  Future<void> rolloverUncookedMeals({
    required String userId,
    DateTime? referenceDate,
  }) {
    final weekStart = startOfWeek(referenceDate ?? DateTime.now());
    final start = formatDate(weekStart);
    return _db.transaction(() async {
      final capacity = await remainingCapacityForWeek(
        userId: userId,
        weekStart: weekStart,
      );
      if (capacity <= 0) return;
      final oldest =
          await (_db.select(_db.mealPlanEntries)
                ..where(
                  (t) =>
                      t.userId.equals(userId) &
                      t.cookedAt.isNull() &
                      t.plannedDate.isSmallerThanValue(start),
                )
                ..orderBy([
                  (t) => OrderingTerm.asc(t.plannedDate),
                  (t) => OrderingTerm.asc(t.id),
                ])
                ..limit(capacity))
              .get();
      for (final entry in oldest) {
        await (_db.update(_db.mealPlanEntries)
              ..where((t) => t.id.equals(entry.id) & t.userId.equals(userId)))
            .write(MealPlanEntriesCompanion(plannedDate: Value(start)));
      }
    });
  }

  /// Marks [entryId] cooked: decrements pantry quantities for every
  /// ingredient of its recipe (unit-normalized against each pantry row,
  /// scaled by `servings`), recording exactly what was removed in
  /// `cooked_adjustments` so [undoCooked] can reverse it precisely
  /// (AC-UX-03). A no-op recipe link (deleted since the entry was created,
  /// AC-MEAL-03) means there is nothing to decrement — only the entry
  /// itself is stamped cooked.
  Future<void> markCooked({
    required int entryId,
    required String userId,
    DateTime? now,
  }) {
    final effectiveNow = now ?? DateTime.now();
    return _db.transaction(() async {
      final entry =
          await (_db.select(_db.mealPlanEntries)
                ..where((t) => t.id.equals(entryId) & t.userId.equals(userId)))
              .getSingleOrNull();
      if (entry == null) {
        throw StateError('Meal plan entry $entryId not found for user $userId');
      }
      if (entry.cookedAt != null) {
        throw StateError('Meal plan entry $entryId is already cooked');
      }

      final recipeId = entry.recipeId;
      String? previousRecipeCookedAt;
      if (recipeId != null) {
        final recipe =
            await (_db.select(_db.recipes)..where(
                  (t) => t.id.equals(recipeId) & t.userId.equals(userId),
                ))
                .getSingle();
        previousRecipeCookedAt = recipe.lastCookedAt;
        final ingredientRows = await (_db.select(_db.recipeIngredients).join([
          innerJoin(
            _db.ingredients,
            _db.ingredients.id.equalsExp(_db.recipeIngredients.ingredientId),
          ),
        ])..where(_db.recipeIngredients.recipeId.equals(recipeId))).get();

        for (final row in ingredientRows) {
          final recipeIngredient = row.readTable(_db.recipeIngredients);
          final ingredient = row.readTable(_db.ingredients);

          final pantryRow =
              await (_db.select(_db.pantryItems)..where(
                    (t) =>
                        t.userId.equals(userId) &
                        t.ingredientId.equals(recipeIngredient.ingredientId),
                  ))
                  .getSingleOrNull();

          var decrementQuantity = recipeQuantityForServings(
            quantity: recipeIngredient.quantity,
            servings: entry.servings,
            yieldCount: recipe.yieldCount,
          );
          if (pantryRow != null) {
            final normalized = normalizeUnit(
              quantity: decrementQuantity,
              unit: recipeIngredient.unit,
              canonicalUnit: pantryRow.unit,
              canonicalName: ingredient.canonicalName,
            );
            if (normalized == null) {
              throw PantryUnitMismatchException(
                ingredientId: ingredient.id,
                canonicalName: ingredient.canonicalName,
                existingUnit: pantryRow.unit,
                incomingUnit: recipeIngredient.unit,
              );
            }
            decrementQuantity = normalized.quantity;
          }

          final delta = await _pantry.decrementForCook(
            userId: userId,
            ingredientId: recipeIngredient.ingredientId,
            amount: decrementQuantity,
            now: effectiveNow,
          );
          if (delta != null) {
            await _db
                .into(_db.cookedAdjustments)
                .insert(
                  CookedAdjustmentsCompanion.insert(
                    userId: userId,
                    mealPlanEntryId: entryId,
                    ingredientId: recipeIngredient.ingredientId,
                    amountDeducted: delta.amountApplied,
                    unit: delta.unit,
                    previousLastUsedAt: Value(delta.previousLastUsedAt),
                    createdAt: effectiveNow.toIso8601String(),
                  ),
                );
          }
        }

        await (_db.update(
          _db.recipes,
        )..where((t) => t.id.equals(recipeId))).write(
          RecipesCompanion(lastCookedAt: Value(effectiveNow.toIso8601String())),
        );
      }

      await (_db.update(
        _db.mealPlanEntries,
      )..where((t) => t.id.equals(entryId))).write(
        MealPlanEntriesCompanion(
          cookedAt: Value(effectiveNow.toIso8601String()),
          previousRecipeCookedAt: Value(previousRecipeCookedAt),
        ),
      );
    });
  }

  /// Reverses [markCooked] exactly: restores every pantry quantity
  /// [markCooked] changed, from the recorded `cooked_adjustments` rows, then
  /// clears them and un-stamps the entry.
  ///
  /// `lastUsedAt` is restored more carefully than quantity (R-15). Quantity
  /// is additive, so reversing it out of order is always safe. `lastUsedAt`
  /// is last-writer-wins: with two plan entries sharing an ingredient (cook
  /// A, then cook B — B's adjustment snapshots the timestamp A's cook just
  /// set), undoing A while B is still standing must *not* stamp the
  /// ingredient back to its pre-A value, or it discards the fact that B is
  /// still cooked and used it more recently. So `lastUsedAt` is only
  /// restored when this adjustment is the *most recent* still-live one for
  /// that ingredient. When a later cook is still standing, this adjustment's
  /// older snapshot is forwarded to the immediate next adjustment before it
  /// is deleted. That preserves the undo chain even when cooks are undone
  /// oldest-first (R-24).
  Future<void> undoCooked({
    required int entryId,
    required String userId,
    DateTime? now,
  }) {
    final effectiveNow = now ?? DateTime.now();
    return _db.transaction(() async {
      final entry =
          await (_db.select(_db.mealPlanEntries)
                ..where((t) => t.id.equals(entryId) & t.userId.equals(userId)))
              .getSingleOrNull();
      if (entry == null) {
        throw StateError('Meal plan entry $entryId not found for user $userId');
      }
      if (entry.cookedAt == null) {
        throw StateError('Meal plan entry $entryId is not cooked');
      }

      final adjustments = await (_db.select(
        _db.cookedAdjustments,
      )..where((t) => t.mealPlanEntryId.equals(entryId))).get();

      for (final adjustment in adjustments) {
        // Is a *later* cook of this same ingredient (from any plan entry)
        // still standing, uncooked-undone? If so, this adjustment is not
        // the most recent word on `lastUsedAt` and must not overwrite it.
        final laterLiveAdjustment =
            await (_db.select(_db.cookedAdjustments)
                  ..where(
                    (t) =>
                        t.userId.equals(userId) &
                        t.ingredientId.equals(adjustment.ingredientId) &
                        t.id.isBiggerThanValue(adjustment.id),
                  )
                  ..orderBy([(t) => OrderingTerm.asc(t.id)])
                  ..limit(1))
                .getSingleOrNull();

        if (laterLiveAdjustment != null) {
          await (_db.update(
            _db.cookedAdjustments,
          )..where((t) => t.id.equals(laterLiveAdjustment.id))).write(
            CookedAdjustmentsCompanion(
              previousLastUsedAt: Value(adjustment.previousLastUsedAt),
            ),
          );
        }

        await _pantry.restoreFromCook(
          userId: userId,
          ingredientId: adjustment.ingredientId,
          amount: adjustment.amountDeducted,
          unit: adjustment.unit,
          previousLastUsedAt: adjustment.previousLastUsedAt,
          now: effectiveNow,
          restoreLastUsedAt: laterLiveAdjustment == null,
        );
      }

      await (_db.delete(
        _db.cookedAdjustments,
      )..where((t) => t.mealPlanEntryId.equals(entryId))).go();

      if (entry.recipeId != null) {
        final later =
            await (_db.select(_db.mealPlanEntries)
                  ..where(
                    (t) =>
                        t.userId.equals(userId) &
                        t.recipeId.equals(entry.recipeId!) &
                        (t.cookedAt.isBiggerThanValue(entry.cookedAt!) |
                            (t.cookedAt.equals(entry.cookedAt!) &
                                t.id.isBiggerThanValue(entry.id))),
                  )
                  ..orderBy([
                    (t) => OrderingTerm.asc(t.cookedAt),
                    (t) => OrderingTerm.asc(t.id),
                  ])
                  ..limit(1))
                .getSingleOrNull();
        if (later != null) {
          await (_db.update(
            _db.mealPlanEntries,
          )..where((t) => t.id.equals(later.id))).write(
            MealPlanEntriesCompanion(
              previousRecipeCookedAt: Value(entry.previousRecipeCookedAt),
            ),
          );
        } else {
          await (_db.update(_db.recipes)..where(
                (t) => t.id.equals(entry.recipeId!) & t.userId.equals(userId),
              ))
              .write(
                RecipesCompanion(
                  lastCookedAt: Value(entry.previousRecipeCookedAt),
                ),
              );
        }
      }
      await (_db.update(
        _db.mealPlanEntries,
      )..where((t) => t.id.equals(entryId))).write(
        const MealPlanEntriesCompanion(
          cookedAt: Value(null),
          previousRecipeCookedAt: Value(null),
        ),
      );
    });
  }
}
