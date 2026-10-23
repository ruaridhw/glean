/// Corpus generation is one pending operation: fetch/save first, then persist entries and shopping gaps in one
/// transaction.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/recipe_proposal.dart';
import 'package:glean/data/util/week.dart';

import '../compression.dart';
import '../food_groups.dart';

class GenerateWeekController extends AsyncNotifier<int> {
  @override
  FutureOr<int> build() => 0;

  Future<void> generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (state.isLoading) return;
    state = const AsyncLoading<int>();
    state = await AsyncValue.guard(
      () => _generate(weekStart: weekStart, slots: slots, servings: servings),
    );
  }

  Future<int> _generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (slots <= 0) return 0;
    final userId = ref.read(currentUserIdProvider);
    final recipes = ref.read(recipesRepositoryProvider);
    final plan = ref.read(planRepositoryProvider);
    final pantry = await ref.read(pantryRepositoryProvider).getAll(userId);
    final saved = await recipes.getSaved(userId);
    final entries = await plan.getWeek(userId: userId, weekStart: weekStart);
    final cooked = await plan.cookedHistory(userId: userId);
    final config = await ref.read(userConfigRepositoryProvider).get(userId);
    final groups = <int, List<String>>{};
    for (final recipe in saved) {
      groups[recipe.id] = await foodGroupsForRecipe(recipes, recipe.id);
    }
    final plannedIds = entries.map((entry) => entry.recipeId).toSet();
    final excluded = <String>{
      for (final entry in entries)
        if (entry.externalIdSnapshot != null) entry.externalIdSnapshot!,
      for (final recipe in saved)
        if (plannedIds.contains(recipe.id) && recipe.externalId != null)
          recipe.externalId!,
    };
    // One clock for the pantry slice and the date it was measured from: across local midnight they
    // must not disagree about which day `expires_in_days` counts from.
    final now = DateTime.now();
    final request = MealPlanRequest(
      source: 'corpus',
      excludeExternalIds: excluded.toList(),
      pantry: compressPantry(pantry, now: now),
      recipeHistory: [
        for (final recipe in saved)
          RecipeHistoryItem(
            recipeId: recipe.id,
            title: recipe.title,
            lastCookedAt: recipe.lastCookedAt,
            foodGroups: groups[recipe.id] ?? [],
          ),
      ],
      cookedHistory: [
        for (final entry in cooked)
          CookedHistoryItem(
            recipeId: entry.externalIdSnapshot,
            title: entry.recipeTitle,
            // UTC, with the offset the wire format needs: a local wall clock read as UTC aged a
            // 41d23h-old cook past the six-week floor in a UTC-7 zone.
            cookedAt: entry.cookedAt!.toUtc(),
            // The latest thumb and its note, if any; the backend keeps a thumbs-down recipe out of the
            // week and reads nothing else from either.
            rating: entry.rating?.dbValue,
            note: entry.note,
          ),
      ],
      foodGroupCoverage: foodGroupCoverageForWeek(entries, groups),
      purchaseTolerance: config.purchaseTolerance,
      mealsPerWeek: slots,
      dietaryFlags: config.dietaryFlags,
      maxActiveTimeMins: config.maxActiveTimeMins,
      localDate: formatDate(now),
    );
    final MealPlanResponse response = await ref
        .read(apiClientProvider)
        .generateMealPlan(request);

    final resolved = <RecipeView>[];
    final seenIds = <int>{};
    for (final pick in response.suggestions) {
      if (resolved.length >= slots) break;
      RecipeView? recipe;
      if (pick.externalId != null) {
        if (!excluded.add(pick.externalId!)) continue;
        recipe = await recipes.getByExternalId(
          externalId: pick.externalId!,
          userId: userId,
        );
        if (recipe == null) {
          // Fetch failures are skipped. Persistence errors remain visible.
          final RecipeOut detail;
          try {
            detail = await ref.read(
              recipeDetailProvider(pick.externalId!).future,
            );
          } catch (_) {
            continue;
          }
          final id = await saveRecipeProposal(recipes, userId, detail);
          recipe = await recipes.getById(id: id, userId: userId);
        }
      } else {
        // Defensive saved-mode compatibility: never accept another user's id.
        recipe = saved.where((value) => value.id == pick.recipeId).firstOrNull;
        if (recipe == null) {
          throw StateError('Meal plan suggested an unknown recipe');
        }
      }
      if (recipe != null && seenIds.add(recipe.id)) resolved.add(recipe);
    }
    if (resolved.isEmpty) return 0;

    return ref.read(gleanDatabaseProvider).transaction(() async {
      // Re-check inside the transaction: manual additions while AI was pending
      // must not overfill the week or duplicate a now-planned recipe.
      final current = await plan.getWeek(userId: userId, weekStart: weekStart);
      final currentIds = current.map((entry) => entry.recipeId).toSet();
      final remaining = await plan.remainingCapacityForWeek(
        userId: userId,
        weekStart: weekStart,
      );
      var inserted = 0;
      for (final recipe in resolved) {
        if (inserted >= remaining) break;
        if (currentIds.contains(recipe.id)) continue;
        final entryId = await plan.addEntry(
          userId: userId,
          recipeId: recipe.id,
          recipeTitle: recipe.title,
          servings: servings,
          plannedDate: weekStart,
        );
        await ref
            .read(shoppingRepositoryProvider)
            .addGapsForRecipe(
              userId: userId,
              recipeId: recipe.id,
              servings: servings,
              sourceMealPlanEntryId: entryId,
            );
        inserted++;
      }
      return inserted;
    });
  }
}

final generateWeekControllerProvider =
    AsyncNotifierProvider<GenerateWeekController, int>(
      GenerateWeekController.new,
    );
