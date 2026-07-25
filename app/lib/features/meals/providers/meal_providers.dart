/// Derived reads for the Meals feature, composed entirely from providers the
/// DATA module already exports (AC-DATA-07: no drift import here, only
/// providers).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/pantry_providers.dart';
import 'package:glean/data/providers/recipes_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';

/// The saved recipe with the family argument (a local recipe id) for the
/// current user, derived from the same [savedRecipesProvider] stream the
/// library list watches. Keeping this a `.watch()`-backed stream all the way
/// down (rather than a one-shot `getById` future) is what makes the detail
/// screen's "to buy"/"in pantry" state — and the recipe disappearing if
/// deleted elsewhere — update live instead of going stale like RN's
/// `useEffect([id])` did (§11, AC-MEAL-11).
final recipeByIdProvider = Provider.family<AsyncValue<RecipeView?>, int>((
  Ref ref,
  int id,
) {
  final AsyncValue<List<RecipeView>> saved = ref.watch(savedRecipesProvider);
  return saved.whenData((List<RecipeView> list) {
    for (final RecipeView recipe in list) {
      if (recipe.id == id) return recipe;
    }
    return null;
  });
});

/// Ingredient rows for the family argument (a local recipe id). A one-shot
/// fetch, not a stream — a saved recipe's own ingredient composition never
/// changes after import (there is no recipe-editing feature). Only *pantry
/// membership* per ingredient can go stale, which [pantryIngredientIdsProvider]
/// tracks separately.
final recipeIngredientsProvider =
    FutureProvider.family<List<RecipeIngredientView>, int>((
      Ref ref,
      int recipeId,
    ) {
      return ref.watch(recipesRepositoryProvider).getIngredients(recipeId);
    });

/// Ingredient ids currently held in the user's pantry, derived from the same
/// [pantryItemsProvider] stream the Pantry tab watches — so "to buy"/"in
/// pantry" badges update live as pantry stock changes.
final pantryIngredientIdsProvider = Provider<AsyncValue<Set<int>>>((Ref ref) {
  final AsyncValue<List<PantryItemView>> items = ref.watch(pantryItemsProvider);
  return items.whenData(
    (List<PantryItemView> list) => <int>{
      for (final PantryItemView item in list) item.ingredientId,
    },
  );
});
