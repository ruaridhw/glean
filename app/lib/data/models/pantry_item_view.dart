// Read-side shape for a pantry item joined with its ingredient and category
// (mirrors the `PantryItem` interface in `mobile/src/types/index.ts`, plus
// `userId`).
//
// `foodGroup` is non-nullable (AC-DATA-11): every row here comes from an
// inner join through `ingredients.category` to `ingredient_categories`, and
// `IngredientsRepository.resolveOrCreate` guarantees any ingredient reached
// through the pantry/shopping intake paths has a valid category — so unlike
// the RN app, there is no nullable-plus-cast here, just a join that
// structurally cannot produce a null food group.
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
  final String category;
  final String foodGroup;
  final int shelfLifeDays;
}
