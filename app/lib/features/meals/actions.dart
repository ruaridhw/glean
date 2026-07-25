/// Shared recipe mutations used by both the saved list (swipe-to-delete) and
/// the detail screen (bookmark unsave) — one implementation, so undo behaves
/// identically everywhere a recipe can be removed (AC-MEAL-02/03, AC-UX-02).
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart'
    show SaveRecipeIngredient;
import 'package:glean/design_system/design_system.dart';

/// Persists an ephemeral API recipe proposal (a search/preview detail fetch
/// or an import-from-URL response) into the saved library, returning the new
/// local id. Shared by `RecipePreviewScreen` (explicit "Save" tap) and
/// `MealsImportScreen` (import always saves once fetched) so the field
/// mapping — including reassembling [NutritionOut] into the JSON shape
/// `RecipeView.nutrition` expects, since that model has no `toJson` of its
/// own — lives in exactly one place.
Future<int> saveApiRecipe(WidgetRef ref, RecipeOut detail) {
  return ref
      .read(recipesRepositoryProvider)
      .save(
        userId: ref.read(currentUserIdProvider),
        externalId: detail.externalId,
        title: detail.title,
        sourceUrl: detail.sourceUrl,
        cuisine: detail.cuisine,
        difficulty: detail.difficulty,
        activeTimeMins: detail.activeTimeMins,
        totalTimeMins: detail.totalTimeMins,
        dietaryFlags: detail.dietaryFlags,
        notSuitableFor: detail.notSuitableFor,
        yieldCount: detail.yieldCount,
        nutrition: _encodeNutrition(detail.nutrition),
        instructions: <RecipeInstructionStep>[
          for (final InstructionOut step in detail.instructions)
            RecipeInstructionStep(
              stepNumber: step.stepNumber,
              phase: step.phase,
              text: step.text,
            ),
        ],
        ingredients: <SaveRecipeIngredient>[
          for (final RecipeIngredientOut ing in detail.ingredients)
            SaveRecipeIngredient(
              canonicalName: ing.canonicalName,
              apiIngredientId: ing.apiIngredientId,
              quantity: ing.quantity,
              unit: ing.unit,
              preparation: ing.preparation,
              isOptional: ing.isOptional,
              substitutions: ing.substitutions,
            ),
        ],
      );
}

String? _encodeNutrition(NutritionOut? nutrition) {
  if (nutrition == null) return null;
  return jsonEncode(<String, double>{
    'calories': nutrition.calories,
    'protein_g': nutrition.proteinG,
    'carbohydrates_g': nutrition.carbohydratesG,
    'fat_g': nutrition.fatG,
    'fibre_g': nutrition.fibreG,
    'sugar_g': nutrition.sugarG,
    'sodium_mg': nutrition.sodiumMg,
  });
}

/// Deletes [recipe] and shows the undo snackbar (AC-UX-02). Does **not**
/// fire a haptic itself — callers differ on whether one already fired
/// (`SwipeToDeleteRow` fires its own `mediumImpact`; a plain bookmark tap
/// must fire its own) — see AC-HAP-03, the RN double-buzz bug.
///
/// Undo re-saves the recipe from a snapshot taken before the delete. This
/// necessarily mints a new row id — SQLite has no "undelete at the same id"
/// primitive — so a plan entry that had already lost its link
/// (`meal_plan_entries.recipeId` is `onDelete: setNull`) when this recipe was
/// first deleted stays unlinked after an undo; only its `recipeTitle`
/// snapshot matters there, and that was never touched by the delete
/// (AC-MEAL-03).
///
/// Both the delete and the undo's re-save are guarded (R-07): neither had a
/// `try`/`catch` before, so a DB-layer failure propagated as an uncaught
/// exception with no feedback at all — the same defect class §11 calls
/// "silent failures" and every other mutation in this feature already
/// guards against. A failed delete leaves the recipe exactly as it was; a
/// failed undo leaves it deleted, but the user is told rather than left to
/// assume undo worked.
Future<void> deleteRecipeWithUndo(
  BuildContext context,
  WidgetRef ref,
  RecipeView recipe,
) async {
  final repository = ref.read(recipesRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);

  // Snapshot the ingredients while the row still exists — after the delete
  // there is nothing left to read them from.
  final ingredients = await repository.getIngredients(recipe.id);

  try {
    await repository.deleteRecipe(id: recipe.id, userId: userId);
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(
        context,
        'Could not remove ${recipe.title}. Try again.',
      );
    }
    return;
  }
  if (!context.mounted) return;

  GleanSnackBar.showUndo(
    context,
    message: '${recipe.title} removed',
    onUndo: () {
      unawaited(() async {
        try {
          await repository.save(
            userId: userId,
            externalId: recipe.externalId,
            title: recipe.title,
            sourceUrl: recipe.sourceUrl,
            cuisine: recipe.cuisine,
            difficulty: recipe.difficulty,
            activeTimeMins: recipe.activeTimeMins,
            totalTimeMins: recipe.totalTimeMins,
            dietaryFlags: recipe.dietaryFlags,
            notSuitableFor: recipe.notSuitableFor,
            yieldCount: recipe.yieldCount,
            nutrition: recipe.nutrition,
            instructions: recipe.instructions,
            ingredients: <SaveRecipeIngredient>[
              for (final ingredient in ingredients)
                SaveRecipeIngredient(
                  canonicalName: ingredient.ingredient.canonicalName,
                  apiIngredientId: ingredient.ingredient.apiIngredientId,
                  quantity: ingredient.quantity,
                  unit: ingredient.unit,
                  preparation: ingredient.preparation,
                  isOptional: ingredient.isOptional,
                  substitutions: ingredient.substitutions,
                ),
            ],
          );
        } catch (_) {
          if (context.mounted) {
            GleanSnackBar.show(context, 'Could not restore ${recipe.title}.');
          }
        }
      }());
    },
  );
}
