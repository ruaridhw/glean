// Read-side shape for a shopping list row. `ingredientId` is non-nullable: every row, including manual
// entries, resolves an ingredient identity via `IngredientsRepository`.
/// Where a shopping row came from. Stored as TEXT in
/// `shopping_list_items.source` using [dbValue].
enum ShoppingSource {
  manual('manual'),
  ai('ai'),
  mealPlan('meal_plan');

  const ShoppingSource(this.dbValue);

  final String dbValue;

  /// Deliberately fail-fast: an unknown stored value means corrupt or newer-schema data, which must surface
  /// rather than be coerced to a default source.
  static ShoppingSource fromDb(String value) => values.firstWhere(
    (s) => s.dbValue == value,
    orElse: () => throw StateError('Unknown shopping source "$value"'),
  );
}

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
  final ShoppingSource source;
  final bool isChecked;

  /// Non-null when inserted as a meal-plan shopping gap; deleting that plan entry cascades this row away.
  final int? sourceMealPlanEntryId;
}
