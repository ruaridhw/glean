// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'catalogue.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

CatalogueGroup _$CatalogueGroupFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'CatalogueGroup',
      json,
      ($checkedConvert) {
        final val = CatalogueGroup(
          id: $checkedConvert('id', (v) => v as String),
          name: $checkedConvert('name', (v) => v as String),
          kind: $checkedConvert('kind', (v) => v as String),
          foodGroup: $checkedConvert('food_group', (v) => v as String),
          trackingMode: $checkedConvert('tracking_mode', (v) => v as String),
          allowedForms: $checkedConvert(
            'allowed_forms',
            (v) => (v as List<dynamic>).map((e) => e as String).toList(),
          ),
          unopenedShelfLifeDays: $checkedConvert(
            'unopened_shelf_life_days',
            (v) => Map<String, int?>.from(v as Map),
          ),
          onceOpenedShelfLifeDays: $checkedConvert(
            'once_opened_shelf_life_days',
            (v) => Map<String, int?>.from(v as Map),
          ),
          stockUnit: $checkedConvert('stock_unit', (v) => v as String?),
        );
        return val;
      },
      fieldKeyMap: const {
        'foodGroup': 'food_group',
        'trackingMode': 'tracking_mode',
        'allowedForms': 'allowed_forms',
        'unopenedShelfLifeDays': 'unopened_shelf_life_days',
        'onceOpenedShelfLifeDays': 'once_opened_shelf_life_days',
        'stockUnit': 'stock_unit',
      },
    );

CatalogueItemOverrides _$CatalogueItemOverridesFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'CatalogueItemOverrides',
  json,
  ($checkedConvert) {
    final val = CatalogueItemOverrides(
      trackingMode: $checkedConvert('tracking_mode', (v) => v as String?),
      stockUnit: $checkedConvert('stock_unit', (v) => v as String?),
      unopenedShelfLifeDays: $checkedConvert(
        'unopened_shelf_life_days',
        (v) => (v as num?)?.toInt(),
      ),
      onceOpenedShelfLifeDays: $checkedConvert(
        'once_opened_shelf_life_days',
        (v) => (v as num?)?.toInt(),
      ),
    );
    return val;
  },
  fieldKeyMap: const {
    'trackingMode': 'tracking_mode',
    'stockUnit': 'stock_unit',
    'unopenedShelfLifeDays': 'unopened_shelf_life_days',
    'onceOpenedShelfLifeDays': 'once_opened_shelf_life_days',
  },
);

CatalogueItemDto _$CatalogueItemDtoFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'CatalogueItemDto',
      json,
      ($checkedConvert) {
        final val = CatalogueItemDto(
          id: $checkedConvert('id', (v) => v as String),
          name: $checkedConvert('name', (v) => v as String),
          group: $checkedConvert('group', (v) => v as String),
          form: $checkedConvert('form', (v) => v as String),
          overrides: $checkedConvert(
            'overrides',
            (v) => CatalogueItemOverrides.fromJson(v as Map<String, dynamic>),
          ),
          source: $checkedConvert('source', (v) => v as String),
          densityGPerMl: $checkedConvert(
            'density_g_per_ml',
            (v) => (v as num?)?.toDouble(),
          ),
          section: $checkedConvert('section', (v) => v as String?),
          formerIds: $checkedConvert(
            'former_ids',
            (v) =>
                (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'densityGPerMl': 'density_g_per_ml',
        'formerIds': 'former_ids',
      },
    );

CatalogueAliasDto _$CatalogueAliasDtoFromJson(Map<String, dynamic> json) =>
    $checkedCreate('CatalogueAliasDto', json, ($checkedConvert) {
      final val = CatalogueAliasDto(
        key: $checkedConvert('key', (v) => v as String),
        name: $checkedConvert('name', (v) => v as String),
        itemId: $checkedConvert('item_id', (v) => v as String),
      );
      return val;
    }, fieldKeyMap: const {'itemId': 'item_id'});

CatalogueSyncResponse _$CatalogueSyncResponseFromJson(
  Map<String, dynamic> json,
) => $checkedCreate('CatalogueSyncResponse', json, ($checkedConvert) {
  final val = CatalogueSyncResponse(
    version: $checkedConvert('version', (v) => (v as num).toInt()),
    groups: $checkedConvert(
      'groups',
      (v) => (v as List<dynamic>)
          .map((e) => CatalogueGroup.fromJson(e as Map<String, dynamic>))
          .toList(),
    ),
    items: $checkedConvert(
      'items',
      (v) => (v as List<dynamic>)
          .map((e) => CatalogueItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    ),
    aliases: $checkedConvert(
      'aliases',
      (v) => (v as List<dynamic>)
          .map((e) => CatalogueAliasDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    ),
  );
  return val;
});
