import 'meal_thumb.dart';

/// Read-side shape for a planned meal. `recipeTitle` is a creation-time snapshot that survives the recipe
/// being deleted, in place of a join to `recipes.title`. [rating] and [note] come from the entry's
/// `meal_ratings` row, joined in the same read rather than fetched per row.
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
    this.rating,
    this.note,
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

  /// The household's thumb on this meal, or null while it is unrated. Only a cooked entry can have one.
  final MealThumb? rating;

  /// The comment saved with [rating], or null when they left none.
  final String? note;

  bool get isCooked => cookedAt != null;
}
