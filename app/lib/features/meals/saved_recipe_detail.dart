/// The saved-recipe detail screen: dish name in the header, a save/unsave bookmark toggle, and a same-screen
/// "Add to plan" mutation with no navigation and no nav param. Reused by [MealDetailScreen] (via `go_router`)
/// and by `RecipePreviewScreen` once a previewed recipe is saved.
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
import 'package:glean/data/providers/viewed_plan_week.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/route_error_screen.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';
import 'presentation.dart';
import 'providers/meal_providers.dart';
import 'widgets/recipe_detail_view.dart';

class SavedRecipeDetail extends ConsumerWidget {
  const SavedRecipeDetail({required this.recipeId, super.key});

  final int recipeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<RecipeView?> recipeAsync = ref.watch(
      recipeByIdProvider(recipeId),
    );

    final bool loading = !recipeAsync.hasValue && !recipeAsync.hasError;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      child: KeyedSubtree(
        key: ValueKey<bool>(loading),
        child: loading
            ? Scaffold(
                appBar: AppBar(title: const Text('Recipe')),
                body: const ListSkeleton(
                  rows: 3,
                  rowHeight: 160,
                  headerHeight: 96,
                ),
              )
            : recipeAsync.when(
                data: (RecipeView? recipe) {
                  // A missing recipe (never existed for this user, or deleted while open) is a recoverable error, never a
                  // permanent spinner: reuse `RouteErrorScreen` rather than `pop()` on a possibly-empty stack.
                  if (recipe == null) {
                    return const RouteErrorScreen(
                      message: 'This recipe could not be found.',
                    );
                  }
                  return _SavedRecipeDetailBody(recipe: recipe);
                },
                loading: () => const SizedBox.shrink(),
                error: (Object error, StackTrace stackTrace) =>
                    const RouteErrorScreen(
                      message: 'This recipe could not be loaded.',
                    ),
              ),
      ),
    );
  }
}

class _SavedRecipeDetailBody extends ConsumerStatefulWidget {
  const _SavedRecipeDetailBody({required this.recipe});
  final RecipeView recipe;
  @override
  ConsumerState<_SavedRecipeDetailBody> createState() =>
      _SavedRecipeDetailBodyState();
}

class _SavedRecipeDetailBodyState
    extends ConsumerState<_SavedRecipeDetailBody> {
  RecipeView get recipe => widget.recipe;
  bool _adding = false;

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<RecipeIngredientView>> ingredientsAsync = ref.watch(
      recipeIngredientsProvider(recipe.id),
    );
    final AsyncValue<Set<int>> pantryIdsAsync = ref.watch(
      pantryIngredientIdsProvider,
    );
    final DateTime weekStart = ref.watch(viewedPlanWeekProvider);
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
        // The dish name, not a static "Recipe".
        title: Text(recipe.title, overflow: TextOverflow.ellipsis),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.bookmark_rounded),
            tooltip: 'Remove from saved recipes',
            onPressed: () => _onUnsave(context, ref),
          ),
        ],
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: KeyedSubtree(
          key: ValueKey<bool>(data == null),
          child: data == null
              ? const ListSkeleton(rows: 3, rowHeight: 160, headerHeight: 96)
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      RecipeDetailView(data: data),
                      const SizedBox(height: 24),
                      _AddToPlanButton(
                        isInPlan: isInPlan,
                        onPressed: _adding
                            ? null
                            : () => _onAddToPlan(
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
      ),
    );
  }

  Future<void> _onUnsave(BuildContext context, WidgetRef ref) async {
    ref.read(hapticsProvider).mediumImpact();
    final deleted = await deleteRecipeWithUndo(context, ref, recipe);
    if (!deleted || !context.mounted) return;
    // Leaving a now-deleted recipe's detail screen follows `RouteErrorScreen`'s rule: this route may have been
    // reached via a deep link with nothing to pop.
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(AppRoutes.meals.path);
    }
  }

  /// Plan-full and already-planned are both checked, and reported via snackbar, before any mutation is
  /// attempted; the user never leaves this screen either way.
  Future<void> _onAddToPlan(
    BuildContext context,
    WidgetRef ref, {
    required bool isInPlan,
    required AsyncValue<int> remaining,
    required int servings,
  }) async {
    if (_adding) return;
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

    setState(() => _adding = true);
    final String userId = ref.read(currentUserIdProvider);
    final weekStart = ref.read(viewedPlanWeekProvider);
    try {
      final message = await ref.read(gleanDatabaseProvider).transaction(() async {
        final plan = ref.read(planRepositoryProvider);
        final entries = await plan.getWeek(
          userId: userId,
          weekStart: weekStart,
        );
        if (entries.any(
          (entry) => entry.recipeId == recipe.id && !entry.isCooked,
        )) {
          return 'Already in your plan for this week.';
        }
        if (await plan.remainingCapacityForWeek(
              userId: userId,
              weekStart: weekStart,
            ) <=
            0) {
          return "This week's plan is full.";
        }
        final entryId = await plan.addEntry(
          userId: userId,
          recipeId: recipe.id,
          recipeTitle: recipe.title,
          servings: servings,
          plannedDate: weekStart,
        );
        final gapsAdded = await ref
            .read(shoppingRepositoryProvider)
            .addGapsForRecipe(
              userId: userId,
              recipeId: recipe.id,
              servings: servings,
              sourceMealPlanEntryId: entryId,
            );
        return gapsAdded > 0
            ? 'Added to plan · $gapsAdded ${gapsAdded == 1 ? 'item' : 'items'} added to your shopping list'
            : 'Added to plan';
      });
      if (message.startsWith('Added to plan')) {
        ref.read(hapticsProvider).mediumImpact();
      }
      if (context.mounted) GleanSnackBar.show(context, message);
    } catch (_) {
      if (context.mounted) {
        GleanSnackBar.show(
          context,
          'Could not add ${recipe.title} to plan. Try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }
}

class _AddToPlanButton extends StatelessWidget {
  const _AddToPlanButton({required this.isInPlan, required this.onPressed});

  final bool isInPlan;
  final VoidCallback? onPressed;

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
