/// Computes real `food_groups`/`food_group_coverage` for `POST /meal-plan`, so the backend's "balance food group
/// coverage across the week" prompt rule is live. Uses each recipe's own ingredients and the same
/// category -> food-group taxonomy as the pantry.
library;

import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/seed/taxonomy.dart';

/// Matches `PantryRepository`'s fallback for an ingredient with no taxonomy category.
const String uncategorisedFoodGroup = 'other';

final Map<String, String> _categoryToFoodGroup = <String, String>{
  for (final CategorySeed seed in ingredientCategorySeeds)
    seed.category: seed.foodGroup,
};

String foodGroupForCategory(String? category) {
  if (category == null) return uncategorisedFoodGroup;
  return _categoryToFoodGroup[category] ?? uncategorisedFoodGroup;
}

/// The distinct food groups [recipeId]'s ingredients cover — what
/// `RecipeHistoryItem.foodGroups` needs populated for real. Sorted for
/// deterministic output (stable request payloads, and easy test
/// assertions).
Future<List<String>> foodGroupsForRecipe(
  RecipesRepository recipes,
  int recipeId,
) async {
  final List<RecipeIngredientView> ingredients = await recipes.getIngredients(
    recipeId,
  );
  final Set<String> groups = <String>{
    for (final RecipeIngredientView ingredient in ingredients)
      foodGroupForCategory(ingredient.ingredient.category),
  };
  return groups.toList()..sort();
}

/// Tally of cooked meals this week per food group: the request's `food_group_coverage`. Only cooked entries
/// count; an entry whose recipe was deleted (`recipeId == null`) or whose food groups aren't in
/// [foodGroupsByRecipeId] is skipped rather than guessed at. A recipe covering several groups increments each.
Map<String, int> foodGroupCoverageForWeek(
  List<MealPlanEntryView> weekEntries,
  Map<int, List<String>> foodGroupsByRecipeId,
) {
  final Map<String, int> coverage = <String, int>{};
  for (final MealPlanEntryView entry in weekEntries) {
    if (!entry.isCooked) continue;
    final int? recipeId = entry.recipeId;
    if (recipeId == null) continue;
    final List<String>? groups = foodGroupsByRecipeId[recipeId];
    if (groups == null) continue;
    for (final String group in groups) {
      coverage[group] = (coverage[group] ?? 0) + 1;
    }
  }
  return coverage;
}
