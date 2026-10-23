// Plan persistence.
//
// - Reads and capacity are week-scoped.
// - `servings` has no default: every `addEntry` call states it, so `preferred_servings` can't be silently
//   hardcoded.
// - Rollover is idempotent: uncooked meals move forward by updating `plannedDate`, not inserting duplicates.
// - `markCooked`/`undoCooked` record and reverse the exact pantry delta via `cooked_adjustments`.
// - Every entry read left-joins its `meal_ratings` row, so a row draws its thumb without a second query.
import 'package:drift/drift.dart';

import '../database.dart';
import '../deletion_snapshots.dart';
import '../models/meal_plan_entry_view.dart';
import '../models/meal_thumb.dart';
import '../models/user_config_view.dart';
import '../util/recipe_servings.dart';
import '../util/unit_normalization.dart';
import '../util/week.dart';
import 'pantry_repository.dart';

/// The history window Generate sends: twelve weeks of cooked meals. The backend leaves out anything cooked
/// in the last six of them, relaxing only when the corpus cannot otherwise fill the week.
const Duration cookedHistoryWindow = Duration(days: 84);

class PlanRepository {
  PlanRepository(this._db, this._pantry);

  final GleanDatabase _db;
  final PantryRepository _pantry;

  /// Entries whose `plannedDate` falls in the week starting [weekStart] (a Monday, see `startOfWeek`), ordered by
  /// date then insertion. Cooked entries are included; callers exclude them from "left to plan" counts via
  /// [MealPlanEntryView.isCooked].
  Stream<List<MealPlanEntryView>> watchWeek({
    required String userId,
    required DateTime weekStart,
  }) => _weekQuery(userId, weekStart).watch().map(_mapEntries);

  /// One-shot twin of [watchWeek]: same query, a plain `.get()` rather than
  /// a subscription opened and immediately cancelled.
  Future<List<MealPlanEntryView>> getWeek({
    required String userId,
    required DateTime weekStart,
  }) async => _mapEntries(await _weekQuery(userId, weekStart).get());

  /// The twelve weeks of cooked meals Generate sends, newest first, each with its rating: the window a
  /// thumbs-down is read from.
  Future<List<MealPlanEntryView>> cookedHistory({
    required String userId,
    DateTime? now,
  }) => cookedSince(
    userId: userId,
    since: (now ?? DateTime.now()).subtract(cookedHistoryWindow),
  );

  /// Meals cooked on or after [since], newest first: the corpus plan avoids repeating them.
  ///
  /// `cookedAt` is stored as an ISO string, so the window is applied to the parsed date rather than compared as
  /// text — a local offset and a `Z` do not sort together. One query, joined to the entry's rating, so the
  /// history the planner reads is also the rated one.
  Future<List<MealPlanEntryView>> cookedSince({
    required String userId,
    required DateTime since,
  }) async {
    final query = _entriesWithRatings()
      ..where(
        _db.mealPlanEntries.userId.equals(userId) &
            _db.mealPlanEntries.cookedAt.isNotNull(),
      );
    final cooked = _mapEntries(
      await query.get(),
    ).where((entry) => !entry.cookedAt!.isBefore(since)).toList();
    cooked.sort((a, b) => b.cookedAt!.compareTo(a.cookedAt!));
    return cooked;
  }

  JoinedSelectStatement _entriesWithRatings() =>
      _db.select(_db.mealPlanEntries).join([
        leftOuterJoin(
          _db.mealRatings,
          _db.mealRatings.mealPlanEntryId.equalsExp(_db.mealPlanEntries.id),
        ),
      ]);

  JoinedSelectStatement _weekQuery(String userId, DateTime weekStart) {
    final start = formatDate(weekStart);
    final end = formatDate(endOfWeek(weekStart));
    return _entriesWithRatings()
      ..where(
        _db.mealPlanEntries.userId.equals(userId) &
            _db.mealPlanEntries.plannedDate.isBiggerOrEqualValue(start) &
            _db.mealPlanEntries.plannedDate.isSmallerThanValue(end),
      )
      ..orderBy([
        OrderingTerm.asc(_db.mealPlanEntries.plannedDate),
        OrderingTerm.asc(_db.mealPlanEntries.id),
      ]);
  }

  List<MealPlanEntryView> _mapEntries(List<TypedResult> rows) =>
      rows.map(_mapEntry).toList();

  MealPlanEntryView _mapEntry(TypedResult row) {
    final MealPlanEntry entry = row.readTable(_db.mealPlanEntries);
    final MealRating? rating = row.readTableOrNull(_db.mealRatings);
    return MealPlanEntryView(
      id: entry.id,
      userId: entry.userId,
      recipeId: entry.recipeId,
      recipeTitle: entry.recipeTitle,
      plannedDate: parseDate(entry.plannedDate),
      cookedAt: entry.cookedAt == null ? null : DateTime.parse(entry.cookedAt!),
      servings: entry.servings,
      externalIdSnapshot: entry.externalIdSnapshot,
      rating: rating == null ? null : MealThumb.fromDb(rating.rating),
      note: rating?.note,
    );
  }

  /// Sets [entryId]'s thumb, or switches it. Writing a different thumb drops the note that described the
  /// old verdict; writing the same one leaves it alone. Only a cooked meal can be rated, because an
  /// uncooked one says nothing reliable about whether the household liked it.
  Future<void> rate({
    required int entryId,
    required String userId,
    required MealThumb rating,
    DateTime? now,
  }) => _db.transaction(() async {
    await _requireCookedEntry(entryId, userId);
    final existing = await _ratingRow(entryId, userId);
    if (existing == null) {
      await _db
          .into(_db.mealRatings)
          .insert(
            MealRatingsCompanion.insert(
              userId: userId,
              mealPlanEntryId: entryId,
              rating: rating.dbValue,
              createdAt: (now ?? DateTime.now()).toUtc().toIso8601String(),
            ),
          );
      return;
    }
    await (_db.update(
      _db.mealRatings,
    )..where((t) => t.id.equals(existing.id))).write(
      MealRatingsCompanion(
        rating: Value(rating.dbValue),
        note: existing.rating == rating.dbValue
            ? const Value.absent()
            : const Value(null),
      ),
    );
  });

  /// Saves a note with [rating] as one write, for the long-press sheet: the thumb and the reason it was
  /// given land together, and a blank note clears an earlier one.
  Future<void> rateWithNote({
    required int entryId,
    required String userId,
    required MealThumb rating,
    required String? note,
    DateTime? now,
  }) => _db.transaction(() async {
    await _requireCookedEntry(entryId, userId);
    final existing = await _ratingRow(entryId, userId);
    final text = (note ?? '').trim();
    if (existing == null) {
      await _db
          .into(_db.mealRatings)
          .insert(
            MealRatingsCompanion.insert(
              userId: userId,
              mealPlanEntryId: entryId,
              rating: rating.dbValue,
              note: Value(text.isEmpty ? null : text),
              createdAt: (now ?? DateTime.now()).toUtc().toIso8601String(),
            ),
          );
      return;
    }
    await (_db.update(
      _db.mealRatings,
    )..where((t) => t.id.equals(existing.id))).write(
      MealRatingsCompanion(
        rating: Value(rating.dbValue),
        note: Value(text.isEmpty ? null : text),
      ),
    );
  });

  /// Clearing the thumb brings the recipe back: the rating row is deleted, and the plan avoids nothing.
  Future<void> clearRating({required int entryId, required String userId}) =>
      (_db.delete(_db.mealRatings)..where(
            (t) => t.mealPlanEntryId.equals(entryId) & t.userId.equals(userId),
          ))
          .go();

  Future<MealRating?> _ratingRow(int entryId, String userId) =>
      (_db.select(_db.mealRatings)..where(
            (t) => t.mealPlanEntryId.equals(entryId) & t.userId.equals(userId),
          ))
          .getSingleOrNull();

  Future<void> _requireCookedEntry(int entryId, String userId) async {
    final entry =
        await (_db.select(_db.mealPlanEntries)
              ..where((t) => t.id.equals(entryId) & t.userId.equals(userId)))
            .getSingleOrNull();
    if (entry == null) {
      throw StateError('No plan entry $entryId for this user');
    }
    if (entry.cookedAt == null) {
      throw StateError('Only a cooked meal can be rated');
    }
  }

  /// Uncooked entries in the week starting [weekStart]: cooked meals stay visible but free up their slot.
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

  /// How many more meals fit in the week starting [weekStart]: `mealsPerWeek` minus the uncooked count, never
  /// negative. Per-week, not lifetime.
  Future<int> remainingCapacityForWeek({
    required String userId,
    required DateTime weekStart,
  }) async {
    final config = await (_db.select(
      _db.userConfig,
    )..where((t) => t.id.equals(userId))).getSingleOrNull();
    final mealsPerWeek =
        config?.mealsPerWeek ?? UserConfigView.defaultMealsPerWeek;
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

  /// Deletes the entry; its plan-derived shopping rows cascade away via `onDelete: cascade`.
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
    final rating =
        await (_db.select(_db.mealRatings)..where(
              (t) => t.mealPlanEntryId.equals(id) & t.userId.equals(userId),
            ))
            .get();
    await deleteEntry(id: id, userId: userId);
    return DeletedPlanEntry(entry, shopping, adjustments, rating);
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
    for (final row in snapshot.rating) {
      await _db.into(_db.mealRatings).insert(row.toCompanion(false));
    }
  });

  Future<void> deleteEntry({required int id, required String userId}) {
    return (_db.delete(
      _db.mealPlanEntries,
    )..where((t) => t.id.equals(id) & t.userId.equals(userId))).go();
  }

  /// Moves every uncooked entry dated before the week starting [referenceDate] (default now) into that week.
  /// It updates `plannedDate` rather than inserting, so repeated calls are no-ops.
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

  /// Marks [entryId] cooked: decrements pantry quantities for each ingredient of its recipe (unit-normalized,
  /// scaled by `servings`), recording what was removed in `cooked_adjustments` so [undoCooked] can reverse it.
  /// If the recipe was deleted since, only the entry is stamped cooked.
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

  /// Reverses [markCooked] exactly: restores every pantry quantity from the recorded `cooked_adjustments`,
  /// then clears them and un-stamps the entry.
  ///
  /// `lastUsedAt` is last-writer-wins, so it is restored only when this adjustment is the most recent live one
  /// for that ingredient; otherwise undoing cook A while cook B stands would erase B's later use. When a later
  /// cook stands, this adjustment's older snapshot is forwarded to the next adjustment before deletion,
  /// preserving the undo chain when cooks are undone oldest-first.
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
      // Undoing the cook takes the thumb with it: only a cooked meal can be rated, and a rating left on
      // an uncooked entry would outlive the meal it described.
      await clearRating(entryId: entryId, userId: userId);
    });
  }
}
