import 'package:json_annotation/json_annotation.dart';

import '../../data/seed/taxonomy.dart';

part 'parsed_ingredient.g.dart';

/// A parsed grocery ingredient with a normalised quantity, returned by all
/// three parse endpoints: `POST /receipts/scan`, `POST /receipts/describe`
/// and `POST /shopping/parse-description`.
///
/// [ingredientGroup], [category] and [foodGroup] are asymmetric on purpose, mirroring the backend
/// (`backend/src/glean/receipts/schemas.py`):
///
/// - [ingredientGroup] and [category] are nullable. The backend coerces an out-of-catalogue or unclassifiable value
///   to `null` rather than failing the response, so one unclassifiable item doesn't fail the whole parse. A backend
///   that predates the group sends only [category]; [groupId] reads whichever is there.
/// - [foodGroup] is required. The backend derives it from the group (falling back to `"other"`), and
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
    this.ingredientGroup,
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

  /// Food group derived deterministically from the ingredient group server-side;
  /// `"other"` when it has none. Required — see the class-level note.
  @JsonKey(fromJson: requireFoodGroup)
  final String foodGroup;

  /// Confidence from 0.0 to 1.0 that the item matches the request.
  final double confidence;

  /// One of the catalogue's ingredient group ids (see `lib/data/seed/ingredient_groups.dart`), or `null` when the
  /// backend couldn't classify it or predates groups.
  final String? ingredientGroup;

  /// One of the 23 older taxonomy values, which the backend sends until every phone reads [ingredientGroup]; `null`
  /// when it has none.
  final String? category;

  /// The ingredient group this item belongs to: the backend's own, else the one the older [category] became.
  String? get groupId => ingredientGroup ?? groupForLegacyCategory(category);

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
