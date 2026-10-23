/// Corpus generation is one reviewed proposal (ADR 0019): create a backend session, poll it to a terminal
/// status while the proposal screen shows its progress, then save the whole week in one transaction when the
/// user taps Add to plan. Nothing reaches the plan before that tap, and a swap is local until it too is saved.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/meal_plan_session.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
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

  /// The polling cadence the session design settles on. Progress lines arrive on the poll that wrote them.
  final Duration interval;

  /// The cap on a run. A session that never reports a terminal status (the network died between create and the
  /// last poll) ends the attempt as `stalled` rather than spinning forever.
  final Duration cap;
}

final generateSessionPollerProvider = Provider<GenerateSessionPoller>(
  (ref) => GenerateSessionPoller(
    sleep: (Duration duration) => Future<void>.delayed(duration),
    now: ref.watch(clockProvider),
  ),
);

/// Which face the proposal screen is showing. The question step is V11: `waiting_for_user` stays [working].
enum GenerateProposalPhase { idle, working, proposal, failed }

/// Everything one Generate attempt holds: its arguments, its progress, its proposal, and the local swaps the
/// user has made but not saved. A swap is a suggestion, not a write; [swaps] and [plannedSwaps] stay in memory
/// until Add to plan commits them.
class GenerateProposalState {
  const GenerateProposalState({
    this.phase = GenerateProposalPhase.idle,
    this.weekStart,
    this.slots = 0,
    this.servings = 0,
    this.sessionId,
    this.progress = const <String>[],
    this.result,
    this.failure,
    this.swaps = const <int, MealPlanRecipe>{},
    this.plannedSwaps = const <int, MealPlanRecipe>{},
    this.saving = false,
  });

  final GenerateProposalPhase phase;

  /// The week the proposal would fill; null when nothing has started.
  final DateTime? weekStart;
  final int slots;
  final int servings;
  final String? sessionId;

  /// Human lines the worker wrote, oldest first, as they arrived.
  final List<String> progress;
  final MealPlanResponse? result;

  /// Set when the attempt ended in a failure. With [result] present it is a failed save, and Retry saves again
  /// rather than planning a new week.
  final GenerateFailure? failure;

  /// Index into `result.suggestions` -> the alternative the user chose. An absent index is the original pick.
  final Map<int, MealPlanRecipe> swaps;

  /// Plan entry id -> the alternative the user chose for a meal already in the week.
  final Map<int, MealPlanRecipe> plannedSwaps;

  /// True while Add to plan resolves recipes and commits; the button is disabled so a double-tap can't run the
  /// transaction twice.
  final bool saving;

  /// The meal a card shows: the chosen alternative when there is one, else the server's suggestion.
  MealPlanRecipe suggestionAt(int index) =>
      swaps[index] ?? result!.suggestions[index];

  bool isSwapped(int index) => swaps.containsKey(index);

  /// True when there is a proposal to show but nothing the user asked to change, so Add to plan has no work: a
  /// done session with an empty suggestion list is the no-meals edge state.
  bool get hasProposal =>
      phase == GenerateProposalPhase.proposal &&
      result != null &&
      result!.suggestions.isNotEmpty;

  GenerateProposalState _copy({
    GenerateProposalPhase? phase,
    String? sessionId,
    List<String>? progress,
    MealPlanResponse? result,
    GenerateFailure? failure,
    Map<int, MealPlanRecipe>? swaps,
    Map<int, MealPlanRecipe>? plannedSwaps,
    bool? saving,
  }) => GenerateProposalState(
    phase: phase ?? this.phase,
    weekStart: weekStart,
    slots: slots,
    servings: servings,
    sessionId: sessionId ?? this.sessionId,
    progress: progress ?? this.progress,
    result: result ?? this.result,
    failure: failure ?? this.failure,
    swaps: swaps ?? this.swaps,
    plannedSwaps: plannedSwaps ?? this.plannedSwaps,
    saving: saving ?? this.saving,
  );
}

class GenerateWeekController extends Notifier<GenerateProposalState> {
  /// Bumped whenever an attempt is superseded (cancel, a new run). A poll or save that finishes after that
  /// must not touch the state it no longer owns.
  int _attempt = 0;

  @override
  GenerateProposalState build() => const GenerateProposalState();

  bool _owns(int attempt) =>
      attempt == _attempt && state.phase == GenerateProposalPhase.working;

  /// Opens the review immediately in its working state, then plans in the background. The screen watches
  /// [state], so the first frame is already the working face rather than a spinner on the Plan tab.
  Future<void> generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (state.phase == GenerateProposalPhase.working) return;
    if (slots <= 0) return;
    final int attempt = ++_attempt;
    state = GenerateProposalState(
      phase: GenerateProposalPhase.working,
      weekStart: weekStart,
      slots: slots,
      servings: servings,
    );
    await _run(attempt, weekStart: weekStart, slots: slots, servings: servings);
  }

  /// Repeats whatever failed: a lost session is planned again; a failed save retries the save from the
  /// proposal already on screen, since resolving and committing are the only work left there. Returns how many
  /// new meals a retried save inserted, so the screen can report it exactly as Add to plan would.
  Future<int> retry() async {
    final GenerateProposalState failed = state;
    if (failed.failure == null) return 0;
    if (failed.result != null) return addToPlan();
    final DateTime? weekStart = failed.weekStart;
    if (weekStart == null) return 0;
    await generate(
      weekStart: weekStart,
      slots: failed.slots,
      servings: failed.servings,
    );
    return 0;
  }

  /// Cancel and Back: stop watching the session, discard everything, and ask the server to cancel it. A
  /// terminal session is left as it was by the server, so calling this after the result is harmless.
  Future<void> cancel() async {
    final String? session = state.sessionId;
    _attempt++;
    state = const GenerateProposalState();
    if (session != null) await _cancelSession(session);
  }

  /// The working state is the whole app here, so a failed DELETE must not trap the user on the screen; the
  /// session expires on its own TTL at worst.
  Future<void> _cancelSession(String sessionId) async {
    try {
      await ref.read(apiClientProvider).cancelMealPlanSession(sessionId);
    } on ApiException catch (_) {
      // Best effort: the discard is already local.
    }
  }

  /// Locally takes the suggestion's alternative, or puts the original back. No network and no write.
  void swapSuggestion(int index) {
    final MealPlanResponse? result = state.result;
    if (result == null || index < 0 || index >= result.suggestions.length) {
      return;
    }
    final Map<int, MealPlanRecipe> next = Map<int, MealPlanRecipe>.of(
      state.swaps,
    );
    if (next.remove(index) == null) {
      final MealPlanRecipe? alternative = result.suggestions[index].alternative;
      if (alternative != null) next[index] = alternative;
    }
    state = state._copy(swaps: next);
  }

  /// Locally swaps a meal already in the week for its planned alternative, or back to the planned meal.
  void swapPlanned(int entryId, MealPlanRecipe alternative) {
    final Map<int, MealPlanRecipe> next = Map<int, MealPlanRecipe>.of(
      state.plannedSwaps,
    );
    if (next.remove(entryId) == null) next[entryId] = alternative;
    state = state._copy(plannedSwaps: next);
  }

  /// Saves the whole review in one transaction: the new meals (with any local swaps applied) into the empty
  /// slots, and a swapped planned meal by updating its own entry. Nothing is written before this call.
  ///
  /// Returns how many new meals were inserted. Recipe details are fetched before the transaction opens, so no
  /// network call runs inside it.
  Future<int> addToPlan() async {
    final GenerateProposalState attempt = state;
    final MealPlanResponse? result = attempt.result;
    final DateTime? weekStart = attempt.weekStart;
    if (result == null || weekStart == null || attempt.saving) return 0;
    state = attempt._copy(saving: true);
    try {
      final String userId = ref.read(currentUserIdProvider);
      final entries = await ref
          .read(planRepositoryProvider)
          .getWeek(userId: userId, weekStart: weekStart);

      final List<MealPlanRecipe> chosen = <MealPlanRecipe>[
        for (int i = 0; i < result.suggestions.length; i++)
          attempt.suggestionAt(i),
      ];
      final List<RecipeView> resolved = await _resolveSuggestions(
        chosen,
        userId: userId,
        entries: entries,
      );

      // Resolve planned swaps before the transaction, for the same reason.
      final List<({int entryId, RecipeView recipe, int servings})>
      plannedUpdates = <({int entryId, RecipeView recipe, int servings})>[];
      for (final MapEntry<int, MealPlanRecipe> swap
          in attempt.plannedSwaps.entries) {
        final MealPlanEntryView? entry = entries
            .where((MealPlanEntryView value) => value.id == swap.key)
            .firstOrNull;
        if (entry == null) continue;
        final RecipeView recipe = await _resolveOne(swap.value, userId: userId);
        plannedUpdates.add((
          entryId: entry.id,
          recipe: recipe,
          servings: entry.servings,
        ));
      }

      if (resolved.isEmpty && plannedUpdates.isEmpty) {
        // The review had meals, so saving none of them is a failure to show, not a quiet no-op.
        throw const GenerateFailure(GenerateFailureKind.unknown);
      }

      final int
      inserted = await ref.read(gleanDatabaseProvider).transaction(() async {
        final plan = ref.read(planRepositoryProvider);
        final shopping = ref.read(shoppingRepositoryProvider);
        // Re-check inside the transaction: manual additions while the review was open must not overfill
        // the week or duplicate a now-planned recipe.
        final List<MealPlanEntryView> current = await plan.getWeek(
          userId: userId,
          weekStart: weekStart,
        );
        final int remaining = await plan.remainingCapacityForWeek(
          userId: userId,
          weekStart: weekStart,
        );
        final Set<int?> currentIds = current
            .map((MealPlanEntryView entry) => entry.recipeId)
            .toSet();
        int count = 0;
        for (final RecipeView recipe in resolved) {
          if (count >= remaining) break;
          if (currentIds.contains(recipe.id)) continue;
          final int entryId = await plan.addEntry(
            userId: userId,
            recipeId: recipe.id,
            recipeTitle: recipe.title,
            servings: attempt.servings,
            plannedDate: weekStart,
          );
          await shopping.addGapsForRecipe(
            userId: userId,
            recipeId: recipe.id,
            servings: attempt.servings,
            sourceMealPlanEntryId: entryId,
          );
          count++;
        }
        for (final ({int entryId, RecipeView recipe, int servings}) update
            in plannedUpdates) {
          await plan.replaceEntryRecipe(
            entryId: update.entryId,
            userId: userId,
            recipeId: update.recipe.id,
            recipeTitle: update.recipe.title,
          );
          await shopping.clearGapsForEntry(
            userId: userId,
            mealPlanEntryId: update.entryId,
          );
          await shopping.addGapsForRecipe(
            userId: userId,
            recipeId: update.recipe.id,
            servings: update.servings,
            sourceMealPlanEntryId: update.entryId,
          );
        }
        return count;
      });
      _attempt++;
      state = const GenerateProposalState();
      return inserted;
    } catch (error) {
      state = attempt._copy(
        phase: GenerateProposalPhase.failed,
        saving: false,
        failure: GenerateFailure.from(error),
      );
      return 0;
    }
  }

  Future<void> _run(
    int attempt, {
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    try {
      final MealPlanRequest request = await _buildRequest(
        weekStart: weekStart,
        slots: slots,
        servings: servings,
      );
      if (!_owns(attempt)) return;

      final api = ref.read(apiClientProvider);
      final MealPlanSessionCreated session;
      try {
        session = await api.createMealPlanSession(request);
      } on ApiException catch (error) {
        _fail(attempt, GenerateFailure.fromApi(error));
        return;
      }
      if (!_owns(attempt)) {
        // Cancelled between create and the first poll: the session exists, so ask the server to drop it.
        await _cancelSession(session.sessionId);
        return;
      }
      state = state._copy(sessionId: session.sessionId);

      final GenerateSessionPoller poller = ref.read(
        generateSessionPollerProvider,
      );
      final DateTime startedAt = poller.now();
      var cursor = 0;
      while (true) {
        if (poller.now().difference(startedAt) >= poller.cap) {
          _fail(attempt, const GenerateFailure(GenerateFailureKind.stalled));
          return;
        }
        try {
          final MealPlanSessionUpdate update = await api.getMealPlanSession(
            session.sessionId,
            after: cursor,
          );
          if (!_owns(attempt)) return;
          cursor = update.nextCursor;
          switch (update.status) {
            case MealPlanSessionStatus.done:
              final MealPlanResponse? result = update.result;
              // A done session that carries no plan is a broken response, not an empty week.
              if (result == null) {
                _fail(
                  attempt,
                  const GenerateFailure(GenerateFailureKind.unknown),
                );
                return;
              }
              state = state._copy(
                phase: GenerateProposalPhase.proposal,
                progress: <String>[...state.progress, ...update.progress],
                result: result,
              );
              return;
            case MealPlanSessionStatus.failed:
              _fail(
                attempt,
                GenerateFailure.fromCode(
                  update.error?.code,
                  retryAfterMinutes: update.error?.retryAfterMinutes,
                ),
              );
              return;
            case MealPlanSessionStatus.cancelled:
              // Only this app cancels its own session; a poll that still sees it stop is a discard, not a
              // failure to show. The screen was already left.
              if (attempt == _attempt) state = const GenerateProposalState();
              return;
            default:
              // queued, running, waiting_for_user (the question is V11) or a status this build does not know:
              // keep the working state and poll again.
              if (update.progress.isNotEmpty) {
                state = state._copy(
                  progress: <String>[...state.progress, ...update.progress],
                );
              }
              break;
          }
        } on ApiException catch (error) {
          // A 404 means the server holds no such session (expired, or never this user's); polling cannot
          // recover it. Anything else is one missed poll, not a failed run: keep polling, and let the cap end
          // the run if they never stop.
          if (error is ApiServerException && error.statusCode == 404) {
            _fail(attempt, const GenerateFailure(GenerateFailureKind.unknown));
            return;
          }
        }
        await poller.sleep(poller.interval);
        if (!_owns(attempt)) return;
      }
    } catch (error) {
      _fail(attempt, GenerateFailure.from(error));
    }
  }

  void _fail(int attempt, GenerateFailure failure) {
    if (!_owns(attempt)) return;
    state = state._copy(
      phase: GenerateProposalPhase.failed,
      failure: failure,
      saving: false,
    );
  }

  /// Resolves the server's picks to recipes saved on this phone, fetching and saving details for corpus recipes
  /// the library does not hold yet. Excludes anything already planned and de-duplicates, exactly as the sync
  /// path did; a detail fetch that fails is skipped so one bad pick does not lose the rest.
  Future<List<RecipeView>> _resolveSuggestions(
    List<MealPlanRecipe> picks, {
    required String userId,
    required List<MealPlanEntryView> entries,
  }) async {
    final recipes = ref.read(recipesRepositoryProvider);
    final saved = await recipes.getSaved(userId);
    final plannedIds = entries
        .map((MealPlanEntryView entry) => entry.recipeId)
        .toSet();
    final excluded = <String>{
      for (final MealPlanEntryView entry in entries)
        if (entry.externalIdSnapshot != null) entry.externalIdSnapshot!,
      for (final RecipeView recipe in saved)
        if (plannedIds.contains(recipe.id) && recipe.externalId != null)
          recipe.externalId!,
    };
    final resolved = <RecipeView>[];
    final seenIds = <int>{};
    for (final MealPlanRecipe pick in picks) {
      RecipeView? recipe;
      if (pick.externalId != null) {
        if (!excluded.add(pick.externalId!)) continue;
        recipe = await _resolveCorpus(pick.externalId!, userId: userId);
        if (recipe == null) continue;
      } else {
        // Defensive saved-mode compatibility: never accept another user's id.
        recipe = saved
            .where((RecipeView value) => value.id == pick.recipeId)
            .firstOrNull;
        if (recipe == null) {
          throw StateError('Meal plan suggested an unknown recipe');
        }
      }
      if (seenIds.add(recipe.id)) resolved.add(recipe);
    }
    return resolved;
  }

  /// Resolves one explicitly chosen meal (a planned meal's swap), where a fetch failure is a failure of the
  /// save rather than a pick to skip.
  Future<RecipeView> _resolveOne(
    MealPlanRecipe pick, {
    required String userId,
  }) async {
    if (pick.externalId != null) {
      final RecipeView? recipe = await _resolveCorpus(
        pick.externalId!,
        userId: userId,
      );
      if (recipe == null) {
        throw StateError('The alternative could not be fetched');
      }
      return recipe;
    }
    final recipes = ref.read(recipesRepositoryProvider);
    final saved = await recipes.getSaved(userId);
    final RecipeView? recipe = saved
        .where((RecipeView value) => value.id == pick.recipeId)
        .firstOrNull;
    if (recipe == null) {
      throw StateError('Meal plan suggested an unknown recipe');
    }
    return recipe;
  }

  /// The saved recipe for a corpus id, fetching and storing its detail when the library does not have it yet.
  /// Returns null when the detail fetch fails.
  Future<RecipeView?> _resolveCorpus(
    String externalId, {
    required String userId,
  }) async {
    final recipes = ref.read(recipesRepositoryProvider);
    final RecipeView? saved = await recipes.getByExternalId(
      externalId: externalId,
      userId: userId,
    );
    if (saved != null) return saved;
    final RecipeOut detail;
    try {
      detail = await ref.read(recipeDetailProvider(externalId).future);
    } catch (_) {
      return null;
    }
    final int id = await saveRecipeProposal(recipes, userId, detail);
    return recipes.getById(id: id, userId: userId);
  }

  Future<MealPlanRequest> _buildRequest({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
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
    return MealPlanRequest(
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
  }
}

final generateWeekControllerProvider =
    NotifierProvider<GenerateWeekController, GenerateProposalState>(
      GenerateWeekController.new,
    );
