// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'parsed_ingredient.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ParsedIngredient _$ParsedIngredientFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'ParsedIngredient',
  json,
  ($checkedConvert) {
    final val = ParsedIngredient(
      name: $checkedConvert('name', (v) => v as String),
      quantity: $checkedConvert('quantity', (v) => (v as num).toDouble()),
      unit: $checkedConvert('unit', (v) => v as String),
      foodGroup: $checkedConvert('food_group', (v) => requireFoodGroup(v)),
      confidence: $checkedConvert('confidence', (v) => (v as num).toDouble()),
      category: $checkedConvert('category', (v) => v as String?),
      unitPrice: $checkedConvert('unit_price', (v) => (v as num?)?.toDouble()),
    );
    return val;
  },
  fieldKeyMap: const {'foodGroup': 'food_group', 'unitPrice': 'unit_price'},
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
