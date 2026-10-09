import 'package:json_annotation/json_annotation.dart';

import 'parsed_ingredient.dart';

part 'shopping.g.dart';

/// Request body for `POST /shopping/parse-description`.
@JsonSerializable(createFactory: false)
class ShoppingParseRequest {
  const ShoppingParseRequest({required this.text});

  final String text;

  Map<String, dynamic> toJson() => _$ShoppingParseRequestToJson(this);
}

/// A shopping-item proposal parsed from a free-text description. Adds [apiIngredientId], the trusted
/// ingredient-catalogue id, still always null until server-side ingredient resolution exists. Inherits
/// `category`/`food_group` from `ParsedIngredient` unchanged: [category] nullable, [foodGroup] required.
@JsonSerializable(fieldRename: FieldRename.snake)
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

  factory ShoppingProposalItem.fromJson(Map<String, dynamic> json) =>
      _$ShoppingProposalItemFromJson(json);

  final String? apiIngredientId;

  @override
  Map<String, dynamic> toJson() => _$ShoppingProposalItemToJson(this);
}

/// Response body for `POST /shopping/parse-description`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class ShoppingParseResponse {
  const ShoppingParseResponse({
    required this.items,
    this.clarifyingQuestions = const [],
  });

  factory ShoppingParseResponse.fromJson(Map<String, dynamic> json) =>
      _$ShoppingParseResponseFromJson(json);

  final List<ShoppingProposalItem> items;
  @JsonKey(defaultValue: <String>[])
  final List<String> clarifyingQuestions;
}
