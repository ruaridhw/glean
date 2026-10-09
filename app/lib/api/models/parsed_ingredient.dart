/// A parsed grocery ingredient with a normalised quantity, returned by all
/// three parse endpoints: `POST /receipts/scan`, `POST /receipts/describe`
/// and `POST /shopping/parse-description`.
///
/// [category] and [foodGroup] are asymmetric on purpose, mirroring the backend
/// (`backend/src/glean/receipts/schemas.py`):
///
/// - [category] is nullable. The backend coerces an out-of-taxonomy or unclassifiable value to `null` rather
///   than failing the response, so one unclassifiable item doesn't fail the whole parse.
/// - [foodGroup] is required. The backend derives it from [category] (falling back to `"other"`), and
///   `POST /meal-plan` validates it non-nullably. A missing `food_group` is a contract violation:
///   [ParsedIngredient.fromJson] throws [FormatException], which [GleanApiClient] turns into an
///   [ApiParseException].
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

  /// One of the 23 ingredient taxonomy values (see `lib/data/seed/taxonomy.dart`), or `null` when the backend
  /// couldn't classify it.
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
