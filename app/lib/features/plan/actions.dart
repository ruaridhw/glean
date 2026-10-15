library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryUnitMismatchException;
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
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

/// Opens the recipe behind a planned meal, inside the Plan tab.
void openPlannedRecipe(BuildContext context, WidgetRef ref, int recipeId) {
  ref.read(hapticsProvider).lightImpact();
  unawaited(
    context.pushNamed(
      AppRoutes.planRecipe.name,
      pathParameters: <String, String>{'id': '$recipeId'},
    ),
  );
}
