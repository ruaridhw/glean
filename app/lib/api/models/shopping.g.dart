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
) => $checkedCreate(
  'ShoppingProposalItem',
  json,
  ($checkedConvert) {
    final val = ShoppingProposalItem(
      name: $checkedConvert('name', (v) => v as String),
      quantity: $checkedConvert('quantity', (v) => (v as num).toDouble()),
      unit: $checkedConvert('unit', (v) => v as String),
      foodGroup: $checkedConvert('food_group', (v) => requireFoodGroup(v)),
      confidence: $checkedConvert('confidence', (v) => (v as num).toDouble()),
      ingredientGroup: $checkedConvert('ingredient_group', (v) => v as String?),
      category: $checkedConvert('category', (v) => v as String?),
      unitPrice: $checkedConvert('unit_price', (v) => (v as num?)?.toDouble()),
    );
    return val;
  },
  fieldKeyMap: const {
    'foodGroup': 'food_group',
    'ingredientGroup': 'ingredient_group',
    'unitPrice': 'unit_price',
  },
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
) => $checkedCreate(
  'ShoppingParseResponse',
  json,
  ($checkedConvert) {
    final val = ShoppingParseResponse(
      items: $checkedConvert(
        'items',
        (v) => (v as List<dynamic>)
            .map(
              (e) => ShoppingProposalItem.fromJson(e as Map<String, dynamic>),
            )
            .toList(),
      ),
      clarifyingQuestions: $checkedConvert(
        'clarifying_questions',
        (v) => (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      ),
    );
    return val;
  },
  fieldKeyMap: const {'clarifyingQuestions': 'clarifying_questions'},
);
