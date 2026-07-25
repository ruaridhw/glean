/// Plan entry mutations shared by the slot list: mark-cooked-with-undo
/// (AC-UX-03) and delete-with-undo (AC-UX-02), plus the empty-slot tap
/// handler. Kept in one place so undo behaves identically everywhere an
/// entry can be removed or cooked — mirrors `lib/features/meals/actions.dart`.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

/// Marks [entry] cooked and shows an undo snackbar wired to
/// `PlanRepository.undoCooked`, which reverses the exact pantry delta
/// `markCooked` applied (AC-UX-03) — not an approximation.
///
/// Fires the ladder's `mediumImpact` itself (committing a data change) —
/// unlike [deleteEntryWithUndo], this isn't reached via `SwipeToDeleteRow`,
/// which would otherwise have already fired one.
Future<void> markCookedWithUndo(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) async {
  final planRepository = ref.read(planRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);

  ref.read(hapticsProvider).mediumImpact();
  await planRepository.markCooked(entryId: entry.id, userId: userId);
  if (!context.mounted) return;

  GleanSnackBar.showUndo(
    context,
    message: '${entry.recipeTitle} marked as cooked',
    onUndo: () {
      unawaited(planRepository.undoCooked(entryId: entry.id, userId: userId));
    },
  );
}

/// Deletes [entry] (cascading its plan-derived shopping rows, AC-SHOP-06)
/// and shows an undo snackbar. Does **not** fire a haptic itself — reached
/// via `SwipeToDeleteRow`, whose `onDismissed` already fires exactly one
/// `mediumImpact` on commit (AC-HAP-03 — the RN app double-buzzed here
/// because both the row and a separate delete button fired their own).
///
/// Undo always re-adds as an *uncooked* entry with the same recipe,
/// servings and planned date. This is a deliberate simplification: `Cooked`
/// already has its own undo at the moment it's marked (AC-UX-03), which is
/// the point where the pantry delta can still be reversed exactly; chaining
/// that reversal into a *later* delete-undo would need to keep a cooked
/// entry's already-cascaded `cooked_adjustments` rows around indefinitely
/// just in case it's later deleted-then-undone, which is unwarranted
/// complexity for what both RN and this port treat as a rare action
/// (deleting a meal you'd already cooked).
///
/// If the entry's recipe was already deleted from the library
/// (`recipeId == null`, AC-MEAL-03's title-only snapshot), there is no
/// recipe id left to re-add with — `PlanRepository.addEntry` requires one
/// — so this shows a plain snackbar with no "Undo" action rather than one
/// that would silently do nothing.
Future<void> deleteEntryWithUndo(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) async {
  final planRepository = ref.read(planRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);

  await planRepository.deleteEntry(id: entry.id, userId: userId);
  if (!context.mounted) return;

  final int? recipeId = entry.recipeId;
  if (recipeId == null) {
    GleanSnackBar.show(context, '${entry.recipeTitle} removed');
    return;
  }

  GleanSnackBar.showUndo(
    context,
    message: '${entry.recipeTitle} removed',
    onUndo: () {
      unawaited(
        planRepository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: entry.recipeTitle,
          servings: entry.servings,
          plannedDate: entry.plannedDate,
        ),
      );
    },
  );
}

/// Tapping an empty "Add a dinner" slot (AC-HAP-05) goes to the Meals tab
/// rather than a dedicated search screen — `AppRoutes.mealsSearch` is
/// intentionally dead (F-09/AC-MEAL-07: one inline search affordance lives
/// inside `MealsScreen`'s Search segment, not a separate pushed route), and
/// "Add to plan" itself is a same-screen mutation on the recipe detail
/// screen (F-05) with no nav param to carry back here. Uses `context.go`
/// (not `goNamed`/`push`) to match the existing cross-tab-navigation
/// convention in `saved_recipe_detail.dart`.
void onAddDinnerTapped(BuildContext context, WidgetRef ref) {
  ref.read(hapticsProvider).lightImpact();
  context.go(AppRoutes.meals.path);
}
