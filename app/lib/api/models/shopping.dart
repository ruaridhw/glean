import 'parsed_ingredient.dart';

/// Request body for `POST /shopping/parse-description`.
class ShoppingParseRequest {
  const ShoppingParseRequest({required this.text});

  final String text;

  Map<String, dynamic> toJson() => {'text': text};
}

/// A shopping-item proposal parsed from a free-text description. Adds [apiIngredientId], the trusted
/// ingredient-catalogue id, still always null until server-side ingredient resolution exists. Inherits
/// `category`/`food_group` from `ParsedIngredient` unchanged: [category] nullable, [foodGroup] required.
class ShoppingProposalItem extends ParsedIngredient {
  const ShoppingProposalItem({
    required super.name,
    required super.quantity,
    required super.unit,
    required super.foodGroup,
    required super.confidence,
    super.category,
    super.unitPrice,
    this.apiIngredientId,
  });

  factory ShoppingProposalItem.fromJson(Map<String, dynamic> json) {
    final base = ParsedIngredient.fromJson(json);
    return ShoppingProposalItem(
      name: base.name,
      quantity: base.quantity,
      unit: base.unit,
      foodGroup: base.foodGroup,
      confidence: base.confidence,
      category: base.category,
      unitPrice: base.unitPrice,
      apiIngredientId: json['api_ingredient_id'] as String?,
    );
  }

  final String? apiIngredientId;

  @override
  Map<String, dynamic> toJson() => {
    ...super.toJson(),
    'api_ingredient_id': apiIngredientId,
  };
}

/// Response body for `POST /shopping/parse-description`.
class ShoppingParseResponse {
  const ShoppingParseResponse({
    required this.items,
    this.clarifyingQuestions = const [],
  });

  factory ShoppingParseResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>;
    final rawQuestions = json['clarifying_questions'] as List<dynamic>?;
    return ShoppingParseResponse(
      items: rawItems
          .map(
            (item) =>
                ShoppingProposalItem.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      clarifyingQuestions:
          rawQuestions?.map((q) => q as String).toList() ?? const [],
    );
  }

  final List<ShoppingProposalItem> items;
  final List<String> clarifyingQuestions;
}
