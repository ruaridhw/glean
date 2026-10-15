// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'catalogue.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

CatalogueGroup _$CatalogueGroupFromJson(Map<String, dynamic> json) =>
    CatalogueGroup(
      id: json['id'] as String,
      name: json['name'] as String,
      kind: json['kind'] as String,
      foodGroup: json['food_group'] as String,
      trackingMode: json['tracking_mode'] as String,
      allowedForms: (json['allowed_forms'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      unopenedShelfLifeDays: Map<String, int?>.from(
        json['unopened_shelf_life_days'] as Map,
      ),
      onceOpenedShelfLifeDays: Map<String, int?>.from(
        json['once_opened_shelf_life_days'] as Map,
      ),
      stockUnit: json['stock_unit'] as String?,
    );

CatalogueItemOverrides _$CatalogueItemOverridesFromJson(
  Map<String, dynamic> json,
) => CatalogueItemOverrides(
  trackingMode: json['tracking_mode'] as String?,
  stockUnit: json['stock_unit'] as String?,
  unopenedShelfLifeDays: (json['unopened_shelf_life_days'] as num?)?.toInt(),
  onceOpenedShelfLifeDays: (json['once_opened_shelf_life_days'] as num?)
      ?.toInt(),
);

CatalogueItemDto _$CatalogueItemDtoFromJson(Map<String, dynamic> json) =>
    CatalogueItemDto(
      id: json['id'] as String,
      name: json['name'] as String,
      group: json['group'] as String,
      form: json['form'] as String,
      overrides: CatalogueItemOverrides.fromJson(
        json['overrides'] as Map<String, dynamic>,
      ),
      source: json['source'] as String,
      densityGPerMl: (json['density_g_per_ml'] as num?)?.toDouble(),
      section: json['section'] as String?,
      formerIds:
          (json['former_ids'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );

CatalogueAliasDto _$CatalogueAliasDtoFromJson(Map<String, dynamic> json) =>
    CatalogueAliasDto(
      key: json['key'] as String,
      name: json['name'] as String,
      itemId: json['item_id'] as String,
    );

CatalogueSyncResponse _$CatalogueSyncResponseFromJson(
  Map<String, dynamic> json,
) => CatalogueSyncResponse(
  version: (json['version'] as num).toInt(),
  groups: (json['groups'] as List<dynamic>)
      .map((e) => CatalogueGroup.fromJson(e as Map<String, dynamic>))
      .toList(),
  items: (json['items'] as List<dynamic>)
      .map((e) => CatalogueItemDto.fromJson(e as Map<String, dynamic>))
      .toList(),
  aliases: (json['aliases'] as List<dynamic>)
      .map((e) => CatalogueAliasDto.fromJson(e as Map<String, dynamic>))
      .toList(),
);
