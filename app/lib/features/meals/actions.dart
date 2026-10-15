library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/recipe_proposal.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';

Future<int> saveApiRecipe(WidgetRef ref, RecipeOut detail) =>
    saveRecipeProposal(
      ref.read(recipesRepositoryProvider),
      ref.read(currentUserIdProvider),
      detail,
    );

/// Returns false on failure so the detail screen does not navigate away.
Future<bool> deleteRecipeWithUndo(
  BuildContext context,
  WidgetRef ref,
  RecipeView recipe,
) {
  final repository = ref.read(recipesRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable(
    context,
    perform: () => repository.deleteWithSnapshot(id: recipe.id, userId: userId),
    undo: (snapshot) =>
        repository.restoreDeleted(snapshot: snapshot, userId: userId),
    message: '${recipe.title} removed',
    failureMessage: 'Could not remove ${recipe.title}. Try again.',
    undoFailureMessage: 'Could not restore ${recipe.title}.',
  );
}
