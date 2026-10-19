// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'shopping.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Map<String, dynamic> _$ShoppingParseRequestToJson(
  ShoppingParseRequest instance,
) => <String, dynamic>{'text': instance.text};

ShoppingProposalItem _$ShoppingProposalItemFromJson(
  Map<String, dynamic> json,
) => ShoppingProposalItem(
  name: json['name'] as String,
  quantity: (json['quantity'] as num).toDouble(),
  unit: json['unit'] as String,
  foodGroup: requireFoodGroup(json['food_group']),
  confidence: (json['confidence'] as num).toDouble(),
  ingredientGroup: json['ingredient_group'] as String?,
  category: json['category'] as String?,
  unitPrice: (json['unit_price'] as num?)?.toDouble(),
);

Map<String, dynamic> _$ShoppingProposalItemToJson(
  ShoppingProposalItem instance,
) => <String, dynamic>{
  'name': instance.name,
  'quantity': instance.quantity,
  'unit': instance.unit,
  'food_group': instance.foodGroup,
  'confidence': instance.confidence,
  'ingredient_group': instance.ingredientGroup,
  'category': instance.category,
  'unit_price': instance.unitPrice,
};

ShoppingParseResponse _$ShoppingParseResponseFromJson(
  Map<String, dynamic> json,
) => ShoppingParseResponse(
  items: (json['items'] as List<dynamic>)
      .map((e) => ShoppingProposalItem.fromJson(e as Map<String, dynamic>))
      .toList(),
  clarifyingQuestions:
      (json['clarifying_questions'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      [],
);
