import 'database.dart';

/// Short-lived Undo receipts retain the exact SQLite identity and cascaded
/// state. Restoration is insert-only and transactional, never an upsert over
/// data the user may have created since deletion.
class DeletedPlanEntry {
  DeletedPlanEntry(
    this.entry,
    List<ShoppingListItem> shopping,
    List<CookedAdjustment> adjustments,
    List<MealRating> rating,
  ) : shopping = List.unmodifiable(shopping),
      adjustments = List.unmodifiable(adjustments),
      rating = List.unmodifiable(rating);
  final MealPlanEntry entry;
  final List<ShoppingListItem> shopping;
  final List<CookedAdjustment> adjustments;

  /// The entry's `meal_ratings` row, at most one, which the delete cascaded away: Undo restores the
  /// household's verdict along with the meal it was about.
  final List<MealRating> rating;
}

class DeletedRecipe {
  DeletedRecipe(
    this.recipe,
    List<RecipeIngredient> ingredients,
    List<RecipeDietaryFlag> flags,
    List<int> linkedEntries,
  ) : ingredients = List.unmodifiable(ingredients),
      flags = List.unmodifiable(flags),
      linkedEntries = List.unmodifiable(linkedEntries);
  final Recipe recipe;
  final List<RecipeIngredient> ingredients;
  final List<RecipeDietaryFlag> flags;
  final List<int> linkedEntries;
}
