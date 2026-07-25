// Read-side shape for a pantry item joined with its ingredient and category
// (mirrors the `PantryItem` interface in `mobile/src/types/index.ts`, plus
// `userId`).
//
// `foodGroup` is non-nullable (AC-DATA-11), but that is enforced by
// coalescing in `PantryRepository._mapRow`, not by requiring the join to
// match: `ingredients.category` is nullable (the ingredient catalog is
// shared, and recipe import can create a category-less ingredient), so a
// pantry item whose ingredient has no taxonomy category still surfaces here
// with `foodGroup == 'other'` — the same fallback the backend and the RN UI
// both already use (FINDINGS.md F-07/F-08) — rather than silently
// disappearing from the list. `category` and `shelfLifeDays` stay honestly
// nullable: there is no fine-grained category to report, and no shelf life
// to infer an expiry from, in that case.
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
