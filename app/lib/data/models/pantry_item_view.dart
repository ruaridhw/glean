// Read-side shape for a pantry item joined with its ingredient and category.
//
// `foodGroup` is non-nullable by coalescing in `PantryRepository._mapRow`: `ingredients.category` is nullable,
// so an item whose ingredient has no taxonomy category surfaces with `foodGroup == 'other'` (the backend's
// fallback too) rather than vanishing. `category` and `shelfLifeDays` stay nullable.
class PantryItemView {
  const PantryItemView({
    required this.id,
    required this.userId,
    required this.ingredientId,
    required this.quantity,
    required this.unit,
    required this.unitPrice,
    required this.expiryDate,
    required this.lastUsedAt,
    required this.updatedAt,
    required this.canonicalName,
    required this.isStaple,
    required this.category,
    required this.foodGroup,
    required this.shelfLifeDays,
  });

  final int id;
  final String userId;
  final int ingredientId;
  final double quantity;
  final String unit;
  final double? unitPrice;
  final DateTime? expiryDate;
  final DateTime? lastUsedAt;
  final DateTime updatedAt;
  final String canonicalName;
  final bool isStaple;
  final String? category;
  final String foodGroup;
  final int? shelfLifeDays;
}
