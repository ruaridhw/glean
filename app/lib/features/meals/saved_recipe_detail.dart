/// The saved-recipe detail screen: shows the dish name in the header
/// (AC-MEAL-06), a real save/unsave bookmark toggle (AC-MEAL-02), and a
/// same-screen "Add to plan" mutation with no navigation and no nav param
/// (AC-MEAL-08/09, FINDINGS.md F-05 — the RN `add_recipe_id` re-add-on-focus
/// bug has no equivalent here to reintroduce).
///
/// Reused by both [MealDetailScreen] (reached via `go_router`, keyed by the
/// saved recipe's local id) and `RecipePreviewScreen` once a previewed
/// recipe has been saved — at that point a preview simply *becomes* this
/// screen, so there is only one implementation of "what a saved recipe looks
/// like".
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/route_error_screen.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';
import 'presentation.dart';
import 'providers/meal_providers.dart';
import 'widgets/meals_skeletons.dart';
import 'widgets/recipe_detail_view.dart';

class SavedRecipeDetail extends ConsumerWidget {
  const SavedRecipeDetail({required this.recipeId, super.key});

  final int recipeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<RecipeView?> recipeAsync = ref.watch(
      recipeByIdProvider(recipeId),
    );

    return recipeAsync.when(
      data: (RecipeView? recipe) {
        // AC-MEAL-12: a missing recipe (never existed for this user, or was
        // deleted while this screen was open) is a recoverable error, never
        // a permanent spinner — reusing `RouteErrorScreen` per its own doc
        // comment rather than calling `pop()` on a possibly-empty stack.
        if (recipe == null) {
          return const RouteErrorScreen(
            message: 'This recipe could not be found.',
          );
        }
        return _SavedRecipeDetailBody(recipe: recipe);
      },
      loading: () => Scaffold(
        appBar: AppBar(title: const Text('Recipe')),
        body: const RecipeDetailSkeleton(),
      ),
      error: (Object error, StackTrace stackTrace) =>
          const RouteErrorScreen(message: 'This recipe could not be loaded.'),
    );
  }
}

class _SavedRecipeDetailBody extends ConsumerWidget {
  const _SavedRecipeDetailBody({required this.recipe});

  final RecipeView recipe;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<RecipeIngredientView>> ingredientsAsync = ref.watch(
      recipeIngredientsProvider(recipe.id),
    );
    final AsyncValue<Set<int>> pantryIdsAsync = ref.watch(
      pantryIngredientIdsProvider,
    );
    final DateTime weekStart = startOfWeek(DateTime.now());
    final AsyncValue<List<MealPlanEntryView>> entriesAsync = ref.watch(
      planWeekProvider(weekStart),
    );
    final AsyncValue<int> remainingAsync = ref.watch(
      planWeekRemainingCapacityProvider(weekStart),
    );
    final AsyncValue<UserConfigView> configAsync = ref.watch(
      userConfigProvider,
    );

    final bool isInPlan = (entriesAsync.value ?? const <MealPlanEntryView>[])
        .any(
          (MealPlanEntryView entry) =>
              entry.recipeId == recipe.id && !entry.isCooked,
        );

    final RecipeDetailData? data = ingredientsAsync.maybeWhen(
      data: (List<RecipeIngredientView> ingredients) =>
          RecipeDetailData.fromSaved(
            recipe: recipe,
            ingredients: ingredients,
            pantryIngredientIds: pantryIdsAsync.value,
          ),
      orElse: () => null,
    );

    return Scaffold(
      appBar: AppBar(
        // AC-MEAL-06: the dish name, not a static "Recipe".
        title: Text(recipe.title, overflow: TextOverflow.ellipsis),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.bookmark_rounded),
            tooltip: 'Remove from saved recipes',
            onPressed: () => _onUnsave(context, ref),
          ),
        ],
      ),
      body: GleanCrossFade(
        showSkeleton: data == null,
        skeleton: const RecipeDetailSkeleton(),
        content: data == null
            ? const SizedBox.shrink()
            : SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    RecipeDetailView(data: data),
                    const SizedBox(height: 24),
                    _AddToPlanButton(
                      isInPlan: isInPlan,
                      onPressed: () => _onAddToPlan(
                        context,
                        ref,
                        isInPlan: isInPlan,
                        remaining: remainingAsync,
                        servings:
                            configAsync.value?.preferredServings ??
                            UserConfigView.defaultPreferredServings,
                      ),
                    ),
                  ],
                ),
              ),
      ),
    );
  }

  Future<void> _onUnsave(BuildContext context, WidgetRef ref) async {
    ref.read(hapticsProvider).mediumImpact();
    await deleteRecipeWithUndo(context, ref, recipe);
    if (!context.mounted) return;
    // Leaving a now-deleted recipe's own detail screen is the same "recover
    // safely, never pop an empty stack" rule `RouteErrorScreen` follows —
    // this route may have been reached via a deep link with nothing to pop.
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(AppRoutes.meals.path);
    }
  }

  /// AC-MEAL-08/09: plan-full and already-planned are both checked — and, if
  /// triggered, reported via snackbar — *before* any mutation is attempted,
  /// and the user never leaves this screen either way.
  Future<void> _onAddToPlan(
    BuildContext context,
    WidgetRef ref, {
    required bool isInPlan,
    required AsyncValue<int> remaining,
    required int servings,
  }) async {
    if (isInPlan) {
      GleanSnackBar.show(context, 'Already in your plan for this week.');
      return;
    }
    if (!remaining.hasValue) {
      GleanSnackBar.show(context, "Couldn't check your plan. Try again.");
      return;
    }
    if (remaining.requireValue <= 0) {
      GleanSnackBar.show(context, "This week's plan is full.");
      return;
    }

    ref.read(hapticsProvider).mediumImpact();
    await ref
        .read(planRepositoryProvider)
        .addEntry(
          userId: ref.read(currentUserIdProvider),
          recipeId: recipe.id,
          recipeTitle: recipe.title,
          servings: servings,
        );
    if (context.mounted) {
      GleanSnackBar.show(context, 'Added to plan');
    }
  }
}

class _AddToPlanButton extends StatelessWidget {
  const _AddToPlanButton({required this.isInPlan, required this.onPressed});

  final bool isInPlan;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: onPressed,
        icon: Icon(
          isInPlan ? Icons.check_circle_rounded : Icons.calendar_month_rounded,
        ),
        label: Text(isInPlan ? 'In plan' : 'Add to plan'),
      ),
    );
  }
}
