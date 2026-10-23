library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/pantry_repository.dart'
    show PantryUnitMismatchException;
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/features/meals/recipe_preview_screen.dart';
import 'package:glean/features/plan/widgets/rating_note_sheet.dart';
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

/// Tapping a thumb on a cooked row: the same thumb again clears the rating, the other one switches it.
///
/// A rating is a write, not a destructive action, so it commits immediately with no confirm and no Undo
/// snackbar — tapping the thumb again is the undo. The first thumb a household ever taps also shows the
/// one-off explainer, after the write, so the rating is never held hostage to a dialog.
Future<void> rateMeal(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
  MealThumb thumb,
) async {
  final repository = ref.read(planRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);
  final bool clearing = entry.rating == thumb;
  try {
    if (clearing) {
      await repository.clearRating(entryId: entry.id, userId: userId);
    } else {
      await repository.rate(entryId: entry.id, userId: userId, rating: thumb);
    }
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(context, 'Could not save your rating. Try again.');
    }
    return;
  }
  ref.read(hapticsProvider).selectionClick();
  if (!context.mounted) return;
  await _explainRatingsOnce(context, ref, userId);
}

/// Long-pressing a thumb: the same rating, with an optional comment, saved in one write.
Future<void> noteMealRating(
  BuildContext context,
  WidgetRef ref,
  MealPlanEntryView entry,
  MealThumb thumb,
) async {
  final String? note = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (BuildContext _) => RatingNoteSheet(entry: entry, thumb: thumb),
  );
  // Skipped or dismissed: the thumb and any existing note stay exactly as they were.
  if (note == null || !context.mounted) return;
  final repository = ref.read(planRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);
  try {
    await repository.rateWithNote(
      entryId: entry.id,
      userId: userId,
      rating: thumb,
      note: note,
    );
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(context, 'Could not save your note. Try again.');
    }
    return;
  }
  ref.read(hapticsProvider).mediumImpact();
  if (!context.mounted) return;
  await _explainRatingsOnce(context, ref, userId);
}

/// The one-off "how ratings are used" explainer: shown on the first thumb this household taps, and never
/// again. It claims the flag before showing, so a second tap cannot open a second copy.
Future<void> _explainRatingsOnce(
  BuildContext context,
  WidgetRef ref,
  String userId,
) async {
  final bool first = await ref
      .read(userConfigRepositoryProvider)
      .claimRatingsExplainer(userId);
  if (!first || !context.mounted) return;
  final AppTokens tokens = context.tokens;
  await showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (BuildContext sheetContext) => SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          tokens.spacing.lg,
          0,
          tokens.spacing.lg,
          tokens.spacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'How ratings work',
              style: Theme.of(sheetContext).textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.md),
            const Text(
              'Thumbs down stops the planner offering that recipe.\n\n'
              'Thumbs up favours it once six weeks have passed.\n\n'
              'Long-press a thumb to add a comment for the planner.',
            ),
            SizedBox(height: tokens.spacing.md),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton(
                onPressed: () => Navigator.of(sheetContext).pop(),
                child: const Text('Got it'),
              ),
            ),
          ],
        ),
      ),
    ),
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
    await context.pushNamed<void>(
      AppRoutes.planRecipe.name,
      pathParameters: <String, String>{'id': '$recipeId'},
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
