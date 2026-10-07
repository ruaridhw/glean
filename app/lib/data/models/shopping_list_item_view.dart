// Read-side shape for a shopping list row — mirrors `ShoppingListItem` in
// the Expo app's `src/types/index.ts` (see git history), plus `userId`.
// `ingredientId` is non-nullable
// (AC-SHOP-03): every row, including manual entries, resolves an ingredient
// identity on the way in via `IngredientsRepository`.
class ShoppingListItemView {
  const ShoppingListItemView({
    required this.id,
    required this.userId,
    required this.ingredientId,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.source,
    required this.isChecked,
    required this.sourceMealPlanEntryId,
    this.memberIds = const [],
  });

  final int id;
  final List<int> memberIds;
  List<int> get ids => memberIds.isEmpty ? [id] : memberIds;
  final String userId;
  final int ingredientId;
  final String name;
  final double? quantity;
  final String? unit;
  final String source;
  final bool isChecked;

  /// Non-null when this row was inserted as a meal-plan shopping gap;
  /// deleting that plan entry cascades this row away (AC-SHOP-06).
  final int? sourceMealPlanEntryId;
}
