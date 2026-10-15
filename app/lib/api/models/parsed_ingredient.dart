import 'package:json_annotation/json_annotation.dart';

part 'parsed_ingredient.g.dart';

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
@JsonSerializable(fieldRename: FieldRename.snake)
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

  factory ParsedIngredient.fromJson(Map<String, dynamic> json) =>
      _$ParsedIngredientFromJson(json);

  /// LLM-normalised concise grocery item name suitable for a shopping list.
  final String name;

  /// Numeric quantity requested or inferred for the item.
  final double quantity;

  /// Practical shopping unit such as "g", "ml", "units", "pack", "bottle".
  final String unit;

  /// Food group derived deterministically from [category] server-side;
  /// `"other"` when [category] is null. Required — see the class-level note.
  @JsonKey(fromJson: requireFoodGroup)
  final String foodGroup;

  /// Confidence from 0.0 to 1.0 that the item matches the request.
  final double confidence;

  /// One of the 23 ingredient taxonomy values (see `lib/data/seed/taxonomy.dart`), or `null` when the backend
  /// couldn't classify it.
  final String? category;

  /// Price per requested unit, when the user provided enough pricing detail.
  final double? unitPrice;

  Map<String, dynamic> toJson() => _$ParsedIngredientToJson(this);
}

/// Decodes `food_group`, which the backend always sends; a missing or empty value is a contract violation.
String requireFoodGroup(Object? value) {
  if (value is! String || value.isEmpty) {
    throw FormatException(
      'ParsedIngredient.food_group missing or empty in response: $value',
    );
  }
  return value;
}
