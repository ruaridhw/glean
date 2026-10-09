/// Derived reads for the Meals feature, composed from the data layer's providers (no drift import).
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/pantry_providers.dart';
import 'package:glean/data/providers/recipes_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';

/// The saved recipe for a local recipe id, derived from the same [savedRecipesProvider] stream the library list
/// watches. Staying stream-based means the detail screen's "to buy"/"in pantry" state, and the recipe
/// disappearing if deleted elsewhere, update live.
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

/// Ingredient rows for a local recipe id. A one-shot fetch: a saved recipe's ingredients never change after
/// import. Only pantry membership can go stale, which [pantryIngredientIdsProvider] tracks.
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
