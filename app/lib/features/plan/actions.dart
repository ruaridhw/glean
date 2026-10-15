/// Plan mutations with feedback and exact, transactional Undo receipts.
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/deletion_snapshots.dart';
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
) async {
  final repository = ref.read(planRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  try {
    await repository.markCooked(entryId: entry.id, userId: userId);
  } catch (error) {
    if (context.mounted) {
      GleanSnackBar.show(
        context,
        error is PantryUnitMismatchException
            ? error.userMessage
            : 'Could not mark ${entry.recipeTitle} as cooked. Try again.',
      );
    }
    return;
  }
  if (!context.mounted) return;
  ref.read(hapticsProvider).mediumImpact();
  GleanSnackBar.showUndo(
    context,
    message: '${entry.recipeTitle} marked as cooked',
    onUndo: () {
      unawaited(() async {
        try {
          await repository.undoCooked(entryId: entry.id, userId: userId);
        } catch (_) {
          if (context.mounted) {
            GleanSnackBar.show(
              context,
              'Could not undo cooking ${entry.recipeTitle}.',
            );
          }
        }
      }());
    },
  );
}

/// Keeps id, cooked state, applied stock delta and shopping ownership. Restoring
/// an uncooked meal also rechecks capacity; a failed Undo cannot half-restore it.
Future<void> deleteEntryWithUndo(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
) async {
  final repository = ref.read(planRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  final DeletedPlanEntry snapshot;
  try {
    snapshot = await repository.deleteWithSnapshot(
      id: entry.id,
      userId: userId,
    );
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(
        context,
        'Could not remove ${entry.recipeTitle}. Try again.',
      );
    }
    return;
  }
  if (!context.mounted) return;
  GleanSnackBar.showUndo(
    context,
    message: '${entry.recipeTitle} removed',
    onUndo: () {
      unawaited(() async {
        try {
          await repository.restoreDeleted(snapshot: snapshot, userId: userId);
        } catch (_) {
          if (context.mounted) {
            GleanSnackBar.show(
              context,
              'Could not restore ${entry.recipeTitle}.',
            );
          }
        }
      }());
    },
  );
}

/// The shared viewed-week provider carries selection into same-screen manual
/// addition. No recipe-id nav parameter can replay a mutation on tab focus.
void onAddDinnerTapped(BuildContext context, WidgetRef ref) {
  ref.read(hapticsProvider).lightImpact();
  context.go(AppRoutes.meals.path);
}
