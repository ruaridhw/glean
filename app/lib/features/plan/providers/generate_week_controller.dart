/// Generation: fetches suggestions from `POST /meal-plan` and persists the
/// accepted ones, as one pending operation from the UI's point of view
/// (AC-PLAN-09/10) — covering both the network round-trip *and* the local
/// commit, unlike watching `generateMealPlanControllerProvider` alone would
/// (its `isLoading` clears the instant the response arrives, before this
/// controller has written anything).
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/providers/meal_plan_providers.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';

import '../compression.dart';
import '../food_groups.dart';

/// Top-up generation for one week (AC-PLAN-06): fills exactly [slots] empty
/// slots, guarded and atomic (AC-PLAN-10) — see [_persist].
class GenerateWeekController extends AsyncNotifier<void> {
  @override
  FutureOr<void> build() {}

  /// Fetches and persists suggestions to fill [slots] empty slots in the
  /// week starting [weekStart], using [servings] for every new entry
  /// (AC-PLAN-07 — never hardcoded to 1).
  ///
  /// Guards against a double-tap firing a second generation while one is
  /// already in flight (AC-PLAN-09) — belt-and-braces alongside the
  /// button's own `onPressed: null` while pending, since either alone could
  /// in principle be bypassed by a test or a future caller.
  Future<void> generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (state.isLoading) return;
    state = const AsyncLoading<void>();
    state = await AsyncValue.guard(
      () => _generate(weekStart: weekStart, slots: slots, servings: servings),
    );
  }

  Future<void> _generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (slots <= 0) return;
    final String userId = ref.read(currentUserIdProvider);

    // One-shot snapshots, not `.watch().first`: this is a command path, not
    // a screen subscription (FLUTTER_MIGRATION.md §3), and opening then
    // immediately cancelling a drift stream here manufactured the deferred
    // teardown-timer churn behind FINDINGS.md F-14.
    final List<PantryItemView> pantryItems = await ref
        .read(pantryRepositoryProvider)
        .getAll(userId);
    final List<RecipeView> savedRecipes = await ref
        .read(recipesRepositoryProvider)
        .getSaved(userId);
    final List<MealPlanEntryView> weekEntries = await ref
        .read(planRepositoryProvider)
        .getWeek(userId: userId, weekStart: weekStart);
    final UserConfigView config = await ref
        .read(userConfigRepositoryProvider)
        .get(userId);

    final Map<int, List<String>> foodGroupsByRecipe = <int, List<String>>{};
    for (final RecipeView recipe in savedRecipes) {
      foodGroupsByRecipe[recipe.id] = await foodGroupsForRecipe(
        ref.read(recipesRepositoryProvider),
        recipe.id,
      );
    }

    final MealPlanRequest request = MealPlanRequest(
      pantry: compressPantry(pantryItems),
      recipeHistory: <RecipeHistoryItem>[
        for (final RecipeView recipe in savedRecipes)
          RecipeHistoryItem(
            recipeId: recipe.id,
            title: recipe.title,
            lastCookedAt: recipe.lastCookedAt,
            foodGroups: foodGroupsByRecipe[recipe.id] ?? const <String>[],
          ),
      ],
      foodGroupCoverage: foodGroupCoverageForWeek(
        weekEntries,
        foodGroupsByRecipe,
      ),
      purchaseTolerance: config.purchaseTolerance,
      mealsPerWeek: slots,
      dietaryFlags: config.dietaryFlags,
      maxActiveTimeMins: config.maxActiveTimeMins,
    );

    final MealPlanResponse? response = await _fetchSuggestions(request);
    final List<MealPlanRecipe> suggestions =
        (response?.suggestions ?? const <MealPlanRecipe>[])
            .take(slots)
            .toList();
    if (suggestions.isEmpty) return;

    await _persist(
      userId: userId,
      suggestions: suggestions,
      savedRecipes: savedRecipes,
      servings: servings,
      weekStart: weekStart,
    );
  }

  /// Delegates the network call to the API module's own command provider
  /// (`generateMealPlanControllerProvider`) rather than reaching for
  /// `apiClientProvider` directly — reads its `.state` off the notifier
  /// instance returned by `.notifier` (not a second `ref.read` of the bare
  /// provider) so an `autoDispose` teardown between the two calls can never
  /// read back a freshly-rebuilt, reset state.
  ///
  /// No keep-alive needed here on our side: that provider now holds itself
  /// alive for the duration of its own network call
  /// (`lib/api/providers/meal_plan_providers.dart`, FINDINGS.md F-15), so a
  /// bare `ref.read(...notifier)` is safe even though nothing else watches
  /// it — an earlier version of this method held a throwaway `ref.listen`
  /// subscription open for exactly this reason; that workaround is gone now
  /// that the provider guarantees it for every caller.
  Future<MealPlanResponse?> _fetchSuggestions(MealPlanRequest request) async {
    final GenerateMealPlanController notifier = ref.read(
      generateMealPlanControllerProvider.notifier,
    );
    await notifier.generate(request);
    final AsyncValue<MealPlanResponse?> result = notifier.state;
    if (result.hasError) {
      Error.throwWithStackTrace(result.error!, result.stackTrace!);
    }
    return result.value;
  }

  /// Guarded and atomic (AC-PLAN-10): every suggestion's `recipe_id` is
  /// validated against the user's real saved-recipe ids *before* any
  /// insert happens, so a hallucinated id aborts the whole batch — nothing
  /// is written — rather than the RN bug, where a bad id thrown mid-loop
  /// left the earlier suggestions already committed with no error shown.
  /// A second line of defence (the `try`/`catch` below, with a compensating
  /// delete of everything already inserted) covers any *other* failure
  /// during the insert loop itself, e.g. an unexpected DB error unrelated
  /// to id validity — so either the whole batch lands, or none of it does,
  /// and the caller always sees the exception (never a silent partial
  /// write).
  Future<void> _persist({
    required String userId,
    required List<MealPlanRecipe> suggestions,
    required List<RecipeView> savedRecipes,
    required int servings,
    required DateTime weekStart,
  }) async {
    final Map<int, String> titleById = <int, String>{
      for (final RecipeView recipe in savedRecipes) recipe.id: recipe.title,
    };

    for (final MealPlanRecipe suggestion in suggestions) {
      if (!titleById.containsKey(suggestion.recipeId)) {
        throw StateError(
          'Meal plan suggested an unknown recipe (id ${suggestion.recipeId})',
        );
      }
    }

    final List<int> insertedEntryIds = <int>[];
    try {
      for (final MealPlanRecipe suggestion in suggestions) {
        final int entryId = await ref
            .read(planRepositoryProvider)
            .addEntry(
              userId: userId,
              recipeId: suggestion.recipeId,
              recipeTitle: titleById[suggestion.recipeId]!,
              servings: servings,
              plannedDate: weekStart,
            );
        insertedEntryIds.add(entryId);
        await ref
            .read(shoppingRepositoryProvider)
            .addGapsForRecipe(
              userId: userId,
              recipeId: suggestion.recipeId,
              servings: servings,
              sourceMealPlanEntryId: entryId,
            );
      }
    } catch (_) {
      for (final int entryId in insertedEntryIds) {
        await ref
            .read(planRepositoryProvider)
            .deleteEntry(id: entryId, userId: userId);
      }
      rethrow;
    }
  }
}

final AsyncNotifierProvider<GenerateWeekController, void>
generateWeekControllerProvider =
    AsyncNotifierProvider<GenerateWeekController, void>(
      GenerateWeekController.new,
    );
