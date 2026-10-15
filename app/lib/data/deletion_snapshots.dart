import 'database.dart';

/// Short-lived Undo receipts retain the exact SQLite identity and cascaded
/// state. Restoration is insert-only and transactional, never an upsert over
/// data the user may have created since deletion.
class DeletedPlanEntry {
  DeletedPlanEntry(
    this.entry,
    List<ShoppingListItem> shopping,
    List<CookedAdjustment> adjustments,
  ) : shopping = List.unmodifiable(shopping),
      adjustments = List.unmodifiable(adjustments);
  final MealPlanEntry entry;
  final List<ShoppingListItem> shopping;
  final List<CookedAdjustment> adjustments;
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
