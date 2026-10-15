import 'package:json_annotation/json_annotation.dart';

part 'catalogue.g.dart';

/// One ingredient group and its default rules, from `GET /catalogue`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class CatalogueGroup {
  const CatalogueGroup({
    required this.id,
    required this.name,
    required this.kind,
    required this.foodGroup,
    required this.trackingMode,
    required this.allowedForms,
    required this.unopenedShelfLifeDays,
    required this.onceOpenedShelfLifeDays,
    this.stockUnit,
  });

  factory CatalogueGroup.fromJson(Map<String, dynamic> json) =>
      _$CatalogueGroupFromJson(json);

  final String id;
  final String name;
  final String kind;
  final String foodGroup;
  final String trackingMode;
  final String? stockUnit;
  final List<String> allowedForms;
  final Map<String, int> unopenedShelfLifeDays;

  /// Null for a form whose opened pack has no limit.
  final Map<String, int?> onceOpenedShelfLifeDays;
}

/// An item's own changes to its group's rules; a null field means the group's rule applies.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class CatalogueItemOverrides {
  const CatalogueItemOverrides({
    this.trackingMode,
    this.stockUnit,
    this.unopenedShelfLifeDays,
    this.onceOpenedShelfLifeDays,
  });

  factory CatalogueItemOverrides.fromJson(Map<String, dynamic> json) =>
      _$CatalogueItemOverridesFromJson(json);

  final String? trackingMode;
  final String? stockUnit;
  final int? unopenedShelfLifeDays;
  final int? onceOpenedShelfLifeDays;
}

/// One catalogue item changed since the requested version.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class CatalogueItemDto {
  const CatalogueItemDto({
    required this.id,
    required this.name,
    required this.group,
    required this.form,
    required this.overrides,
    required this.source,
    this.densityGPerMl,
  });

  factory CatalogueItemDto.fromJson(Map<String, dynamic> json) =>
      _$CatalogueItemDtoFromJson(json);

  final String id;
  final String name;
  final String group;
  final String form;
  final CatalogueItemOverrides overrides;
  @JsonKey(name: 'density_g_per_ml')
  final double? densityGPerMl;

  /// `seed`, or `llm` for a provisional item.
  final String source;
}

/// A name, canonical or alias, that resolves to a catalogue item. [key] is what lookups match on.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class CatalogueAliasDto {
  const CatalogueAliasDto({
    required this.key,
    required this.name,
    required this.itemId,
  });

  factory CatalogueAliasDto.fromJson(Map<String, dynamic> json) =>
      _$CatalogueAliasDtoFromJson(json);

  final String key;
  final String name;
  final String itemId;
}

/// Response body for `GET /catalogue?since=<version>`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class CatalogueSyncResponse {
  const CatalogueSyncResponse({
    required this.version,
    required this.groups,
    required this.items,
    required this.aliases,
  });

  factory CatalogueSyncResponse.fromJson(Map<String, dynamic> json) =>
      _$CatalogueSyncResponseFromJson(json);

  /// The version this response brings the device up to; send it as `since` next time.
  final int version;
  final List<CatalogueGroup> groups;
  final List<CatalogueItemDto> items;
  final List<CatalogueAliasDto> aliases;
}
