/// A parsed grocery ingredient with a normalised quantity, returned by all
/// three parse endpoints: `POST /receipts/scan`, `POST /receipts/describe`
/// and `POST /shopping/parse-description`.
///
/// **Shipped contract (FLUTTER_MIGRATION.md §9, AC-BE-04, `55ba23f`,
/// `backend/src/glean/receipts/schemas.py`):** [category] and [foodGroup]
/// are asymmetric on purpose, mirroring the backend's own asymmetry —
///
/// - [category] stays **nullable**. The backend coerces an out-of-taxonomy
///   or genuinely unclassifiable LLM value to `null` (logged server-side)
///   rather than failing the whole response. Modelling it as required here
///   would turn that deliberate, survivable degradation into a hard client
///   failure — one unclassifiable item in a 20-item receipt would fail the
///   *entire* parse. [category] only drives finer-grained, degrade-gracefully
///   features (pantry grouping detail, per-category shelf-life inference), so
///   `null` is a fine answer for it.
/// - [foodGroup] stays **required** (non-nullable `String`). The backend
///   computes it deterministically from [category], falling back to
///   `"other"` when [category] is null — so it is *never* absent in a
///   well-formed response, and it is the field `POST /meal-plan` validates
///   non-nullably (AC-DATA-11). A response missing `food_group` is a genuine
///   contract violation, not a degradable edge case, so
///   [ParsedIngredient.fromJson] throws [FormatException] for that case —
///   which [GleanApiClient] turns into an [ApiParseException] rather than
///   crashing or silently defaulting.
class ParsedIngredient {
  const ParsedIngredient({
    required this.name,
    required this.quantity,
    required this.unit,
    required this.foodGroup,
    required this.confidence,
    this.category,
    this.unitPrice,
  });

  factory ParsedIngredient.fromJson(Map<String, dynamic> json) {
    final foodGroup = json['food_group'];
    if (foodGroup is! String || foodGroup.isEmpty) {
      throw FormatException(
        'ParsedIngredient.food_group missing or empty in response: $json',
      );
    }
    return ParsedIngredient(
      name: json['name'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      unit: json['unit'] as String,
      foodGroup: foodGroup,
      confidence: (json['confidence'] as num).toDouble(),
      category: json['category'] as String?,
      unitPrice: (json['unit_price'] as num?)?.toDouble(),
    );
  }

  /// LLM-normalised concise grocery item name suitable for a shopping list.
  final String name;

  /// Numeric quantity requested or inferred for the item.
  final double quantity;

  /// Practical shopping unit such as "g", "ml", "units", "pack", "bottle".
  final String unit;

  /// Food group derived deterministically from [category] server-side;
  /// `"other"` when [category] is null. Required — see the class-level note.
  final String foodGroup;

  /// Confidence from 0.0 to 1.0 that the item matches the request.
  final double confidence;

  /// One of the 23-category ingredient taxonomy values (see
  /// `mobile/src/db/ingredient-categories.ts` for the current list, ported
  /// to the DATA module), or `null` when the backend couldn't classify it.
  /// Nullable — see the class-level note.
  final String? category;

  /// Price per requested unit, when the user provided enough pricing detail.
  final double? unitPrice;

  Map<String, dynamic> toJson() => {
    'name': name,
    'quantity': quantity,
    'unit': unit,
    'food_group': foodGroup,
    'confidence': confidence,
    'category': category,
    'unit_price': unitPrice,
  };
}
