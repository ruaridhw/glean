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

/// A shopping-item proposal parsed from a free-text description: the fields every parse endpoint returns, unchanged.
@JsonSerializable(fieldRename: FieldRename.snake)
class ShoppingProposalItem extends ParsedIngredient {
  const ShoppingProposalItem({
    required super.name,
    required super.quantity,
    required super.unit,
    required super.foodGroup,
    required super.confidence,
    super.ingredientGroup,
    super.category,
    super.unitPrice,
  });

  factory ShoppingProposalItem.fromJson(Map<String, dynamic> json) =>
      _$ShoppingProposalItemFromJson(json);

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
