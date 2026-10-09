/// Recipe save and destructive Undo shared by saved-list and detail actions.
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/data/deletion_snapshots.dart';
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

/// Snapshot/read/delete and restore are each atomic. Undo retains the recipe
/// identity, ingredients and surviving plan links instead of minting a new id.
/// Returns false on failure so the detail screen must not navigate away.
Future<bool> deleteRecipeWithUndo(
  BuildContext context,
  WidgetRef ref,
  RecipeView recipe,
) async {
  final repository = ref.read(recipesRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  final messenger = ScaffoldMessenger.of(context);
  final DeletedRecipe snapshot;
  try {
    snapshot = await repository.deleteWithSnapshot(
      id: recipe.id,
      userId: userId,
    );
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(
        context,
        'Could not remove ${recipe.title}. Try again.',
      );
    }
    return false;
  }
  if (!context.mounted) return true;
  GleanSnackBar.showUndo(
    context,
    message: '${recipe.title} removed',
    onUndo: () {
      unawaited(() async {
        try {
          await repository.restoreDeleted(snapshot: snapshot, userId: userId);
        } catch (_) {
          if (messenger.mounted) {
            GleanSnackBar.showOn(
              messenger,
              'Could not restore ${recipe.title}.',
            );
          }
        }
      }());
    },
  );
  return true;
}
