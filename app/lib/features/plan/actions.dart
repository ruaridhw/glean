library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryUnitMismatchException;
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/features/meals/recipe_preview_screen.dart';
import 'package:go_router/go_router.dart';

Future<void> markCookedWithUndo(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) {
  final repository = ref.read(planRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable<void>(
    context,
    perform: () => repository.markCooked(entryId: entry.id, userId: userId),
    undo: (_) => repository.undoCooked(entryId: entry.id, userId: userId),
    message: '${entry.recipeTitle} marked as cooked',
    failureMessage: 'Could not mark ${entry.recipeTitle} as cooked. Try again.',
    undoFailureMessage: 'Could not undo cooking ${entry.recipeTitle}.',
    describeError: (error) => error is PantryUnitMismatchException
        ? error.userMessage
        : 'Could not mark ${entry.recipeTitle} as cooked. Try again.',
    onSuccess: ref.read(hapticsProvider).mediumImpact,
  );
}

/// Undo keeps cooked state and applied stock delta; an uncooked meal's capacity
/// is rechecked on restore.
Future<void> deleteEntryWithUndo(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) {
  final repository = ref.read(planRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable(
    context,
    perform: () => repository.deleteWithSnapshot(id: entry.id, userId: userId),
    undo: (snapshot) =>
        repository.restoreDeleted(snapshot: snapshot, userId: userId),
    message: '${entry.recipeTitle} removed',
    failureMessage: 'Could not remove ${entry.recipeTitle}. Try again.',
    undoFailureMessage: 'Could not restore ${entry.recipeTitle}.',
  );
}

void onAddDinnerTapped(BuildContext context, WidgetRef ref) {
  ref.read(hapticsProvider).lightImpact();
  context.go(AppRoutes.meals.path);
}

/// The external id a deleted recipe can still be previewed by, or null when the entry has none worth trying.
String? previewableExternalId(MealPlanEntryView entry) {
  final String? id = entry.externalIdSnapshot?.trim();
  return id == null || id.isEmpty ? null : id;
}

/// Whether tapping [entry] has anywhere to go: its saved recipe, or a snapshot id to preview.
bool canOpenPlannedRecipe(MealPlanEntryView entry) =>
    entry.recipeId != null || previewableExternalId(entry) != null;

/// Opens the recipe behind a planned meal, inside the Plan tab. A saved recipe opens its detail screen. A deleted
/// one is previewed from its external-id snapshot, but only once the backend has resolved that id: an id that no
/// longer resolves (e.g. a deleted URL import) says so and stays on Plan instead of navigating to a dead end.
Future<void> openPlannedRecipe(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) async {
  ref.read(hapticsProvider).lightImpact();
  final int? recipeId = entry.recipeId;
  if (recipeId != null) {
    unawaited(
      context.pushNamed(
        AppRoutes.planRecipe.name,
        pathParameters: <String, String>{'id': '$recipeId'},
      ),
    );
    return;
  }
  final String? externalId = previewableExternalId(entry);
  if (externalId == null) return;

  // Keeps the fetched recipe alive so the preview screen reuses it instead of fetching again.
  final ProviderSubscription<AsyncValue<RecipeOut>> subscription = ref
      .listenManual(recipeDetailProvider(externalId), (_, _) {});
  try {
    await ref.read(recipeDetailProvider(externalId).future);
  } catch (_) {
    subscription.close();
    if (context.mounted) {
      GleanSnackBar.show(context, 'Recipe removed');
    }
    return;
  }
  if (!context.mounted) {
    subscription.close();
    return;
  }
  await Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => RecipePreviewScreen(externalId: externalId),
    ),
  );
  subscription.close();
}
