/// Shared mapping from an ephemeral API proposal to the local recipe library.
library;

import 'dart:convert';
import 'package:glean/api/models/recipes.dart';
import '../models/recipe_view.dart';
import '../repositories/recipes_repository.dart';

Future<int> saveRecipeProposal(
  RecipesRepository repository,
  String userId,
  RecipeOut detail,
) {
  final nutrition = detail.nutrition;
  return repository.save(
    userId: userId,
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
    nutrition: nutrition == null
        ? null
        : jsonEncode({
            'calories': nutrition.calories,
            'protein_g': nutrition.proteinG,
            'carbohydrates_g': nutrition.carbohydratesG,
            'fat_g': nutrition.fatG,
            'fibre_g': nutrition.fibreG,
            'sugar_g': nutrition.sugarG,
            'sodium_mg': nutrition.sodiumMg,
          }),
    instructions: [
      for (final step in detail.instructions)
        RecipeInstructionStep(
          stepNumber: step.stepNumber,
          phase: step.phase,
          text: step.text,
        ),
    ],
    ingredients: [
      for (final ing in detail.ingredients)
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
