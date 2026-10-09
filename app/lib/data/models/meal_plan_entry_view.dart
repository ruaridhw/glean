// Read-side shape for a planned meal. `recipeTitle` is a creation-time snapshot that survives the recipe
// being deleted, in place of a join to `recipes.title`.
class MealPlanEntryView {
  const MealPlanEntryView({
    required this.id,
    required this.userId,
    required this.recipeId,
    required this.recipeTitle,
    required this.plannedDate,
    required this.cookedAt,
    required this.servings,
    this.externalIdSnapshot,
  });

  final int id;
  final String userId;

  /// Null once the underlying recipe has been deleted; the entry still exists and shows [recipeTitle].
  final int? recipeId;
  final String recipeTitle;
  final DateTime plannedDate;
  final DateTime? cookedAt;
  final int servings;
  final String? externalIdSnapshot;

  bool get isCooked => cookedAt != null;
}
