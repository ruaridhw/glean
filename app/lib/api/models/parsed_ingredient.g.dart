// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'parsed_ingredient.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ParsedIngredient _$ParsedIngredientFromJson(Map<String, dynamic> json) =>
    ParsedIngredient(
      name: json['name'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      unit: json['unit'] as String,
      foodGroup: requireFoodGroup(json['food_group']),
      confidence: (json['confidence'] as num).toDouble(),
      category: json['category'] as String?,
      unitPrice: (json['unit_price'] as num?)?.toDouble(),
    );

Map<String, dynamic> _$ParsedIngredientToJson(ParsedIngredient instance) =>
    <String, dynamic>{
      'name': instance.name,
      'quantity': instance.quantity,
      'unit': instance.unit,
      'food_group': instance.foodGroup,
      'confidence': instance.confidence,
      'category': instance.category,
      'unit_price': instance.unitPrice,
    };
