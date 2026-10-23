/// Corpus generation is one pending operation: create a backend session, poll it to a terminal status, then
/// fetch/save and persist entries and shopping gaps in one transaction.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/meal_plan_session.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/recipe_proposal.dart';
import 'package:glean/data/util/week.dart';

import '../compression.dart';
import '../food_groups.dart';
import '../generate_failure.dart';

/// How the session loop waits and measures. Injected so a test can drive the whole 1 s cadence and the 5 min cap
/// without real delays: production sleeps for real and reads the wall clock.
class GenerateSessionPoller {
  const GenerateSessionPoller({
    required this.sleep,
    required this.now,
    this.interval = const Duration(seconds: 1),
    this.cap = const Duration(minutes: 5),
  });

  final Future<void> Function(Duration) sleep;
  final DateTime Function() now;

  /// The polling cadence the session design settles on. Polling faster would multiply the backend's read
  /// traffic for no visible gain (V1 shows a spinner, not progress lines).
  final Duration interval;

  /// The V1 cap on a run. A session that never reports a terminal status (the network died between create and
  /// the last poll) ends the attempt as `stalled` rather than spinning forever.
  final Duration cap;
}

final generateSessionPollerProvider = Provider<GenerateSessionPoller>(
  (ref) => GenerateSessionPoller(
    sleep: (Duration duration) => Future<void>.delayed(duration),
    now: ref.watch(clockProvider),
  ),
);

/// The arguments of one Generate attempt, kept so the error snackbar's Retry can repeat exactly the same one. A
/// failed attempt never writes, so the slots it asked for are still the right ones.
class _GenerateArgs {
  const _GenerateArgs({
    required this.weekStart,
    required this.slots,
    required this.servings,
  });

  final DateTime weekStart;
  final int slots;
  final int servings;
}

class GenerateWeekController extends AsyncNotifier<int> {
  _GenerateArgs? _lastAttempt;

  @override
  FutureOr<int> build() => 0;

  Future<void> generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (state.isLoading) return;
    _lastAttempt = _GenerateArgs(
      weekStart: weekStart,
      slots: slots,
      servings: servings,
    );
    state = const AsyncLoading<int>();
    state = await AsyncValue.guard(
      () => _generate(weekStart: weekStart, slots: slots, servings: servings),
    );
  }

  /// Repeats the last attempt, for the failure snackbar's Retry action.
  Future<void> retry() async {
    final _GenerateArgs? last = _lastAttempt;
    if (last == null) return;
    await generate(
      weekStart: last.weekStart,
      slots: last.slots,
      servings: last.servings,
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
    // The window plus any older cook that still carries a thumbs down: a dislike does not expire.
    final cooked = await plan.plannerHistory(userId: userId);
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
    final MealPlanResponse response = await _runSession(request);

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

  /// Creates a session and polls it to a terminal status, then returns the meal plan it produced. Every way the
  /// attempt can end is a [GenerateFailure], so the Plan tab renders one catalogue however it failed.
  Future<MealPlanResponse> _runSession(MealPlanRequest request) async {
    final api = ref.read(apiClientProvider);
    final GenerateSessionPoller poller = ref.read(
      generateSessionPollerProvider,
    );
    final MealPlanSessionCreated session;
    try {
      session = await api.createMealPlanSession(request);
    } on ApiException catch (error) {
      throw GenerateFailure.fromApi(error);
    }
    final DateTime startedAt = poller.now();
    var cursor = 0;
    while (true) {
      if (poller.now().difference(startedAt) >= poller.cap) {
        throw const GenerateFailure(GenerateFailureKind.stalled);
      }
      try {
        final MealPlanSessionUpdate update = await api.getMealPlanSession(
          session.sessionId,
          after: cursor,
        );
        cursor = update.cursor;
        switch (update.status) {
          case MealPlanSessionStatus.done:
            final MealPlanResponse? result = update.result;
            // A done session that carries no plan is a broken response, not an empty week.
            if (result == null) {
              throw const GenerateFailure(GenerateFailureKind.unknown);
            }
            return result;
          case MealPlanSessionStatus.failed:
            throw GenerateFailure.fromCode(
              update.error?.code,
              retryAfterMinutes: update.error?.retryAfterMinutes,
            );
          default:
            // queued, running, waiting_for_user (V3 answers those) or a status this build does not know:
            // poll again.
            break;
        }
      } on ApiException catch (error) {
        // A 404 means the server holds no such session (expired, or never this user's); polling cannot
        // recover it. Anything else is one missed poll, not a failed run: keep polling, and let the cap end
        // the run if they never stop.
        if (error is ApiServerException && error.statusCode == 404) {
          throw const GenerateFailure(GenerateFailureKind.unknown);
        }
      }
      await poller.sleep(poller.interval);
    }
  }
}

final generateWeekControllerProvider =
    AsyncNotifierProvider<GenerateWeekController, int>(
      GenerateWeekController.new,
    );
