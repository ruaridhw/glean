// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recipes.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

RecipeIngredientOut _$RecipeIngredientOutFromJson(Map<String, dynamic> json) =>
    RecipeIngredientOut(
      canonicalName: json['canonical_name'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      unit: json['unit'] as String,
      apiIngredientId: json['api_ingredient_id'] as String?,
      preparation: json['preparation'] as String?,
      isOptional: json['is_optional'] as bool? ?? false,
      substitutions:
          (json['substitutions'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );

NutritionOut _$NutritionOutFromJson(Map<String, dynamic> json) => NutritionOut(
  calories: (json['calories'] as num?)?.toDouble() ?? 0.0,
  proteinG: (json['protein_g'] as num?)?.toDouble() ?? 0.0,
  carbohydratesG: (json['carbohydrates_g'] as num?)?.toDouble() ?? 0.0,
  fatG: (json['fat_g'] as num?)?.toDouble() ?? 0.0,
  fibreG: (json['fibre_g'] as num?)?.toDouble() ?? 0.0,
  sugarG: (json['sugar_g'] as num?)?.toDouble() ?? 0.0,
  sodiumMg: (json['sodium_mg'] as num?)?.toDouble() ?? 0.0,
);

InstructionOut _$InstructionOutFromJson(Map<String, dynamic> json) =>
    InstructionOut(
      stepNumber: (json['step_number'] as num).toInt(),
      phase: json['phase'] as String,
      text: json['text'] as String,
    );

RecipeOut _$RecipeOutFromJson(Map<String, dynamic> json) => RecipeOut(
  externalId: json['external_id'] as String,
  title: json['title'] as String,
  sourceUrl: json['source_url'] as String?,
  cuisine: json['cuisine'] as String?,
  difficulty: json['difficulty'] as String?,
  activeTimeMins: (json['active_time_mins'] as num?)?.toInt(),
  totalTimeMins: (json['total_time_mins'] as num?)?.toInt(),
  dietaryFlags:
      (json['dietary_flags'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      [],
  notSuitableFor:
      (json['not_suitable_for'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      [],
  yieldCount: (json['yield_count'] as num?)?.toInt(),
  nutrition: json['nutrition'] == null
      ? null
      : NutritionOut.fromJson(json['nutrition'] as Map<String, dynamic>),
  instructions:
      (json['instructions'] as List<dynamic>?)
          ?.map((e) => InstructionOut.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
  ingredients:
      (json['ingredients'] as List<dynamic>?)
          ?.map((e) => RecipeIngredientOut.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
);

RecipeSearchResult _$RecipeSearchResultFromJson(Map<String, dynamic> json) =>
    RecipeSearchResult(
      externalId: json['external_id'] as String,
      title: json['title'] as String,
      cuisine: json['cuisine'] as String?,
      difficulty: json['difficulty'] as String?,
      totalTimeMins: (json['total_time_mins'] as num?)?.toInt(),
      dietaryFlags:
          (json['dietary_flags'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );

RecipeSearchResponse _$RecipeSearchResponseFromJson(
  Map<String, dynamic> json,
) => RecipeSearchResponse(
  results: (json['results'] as List<dynamic>)
      .map((e) => RecipeSearchResult.fromJson(e as Map<String, dynamic>))
      .toList(),
  total: (json['total'] as num).toInt(),
);

Map<String, dynamic> _$ImportUrlRequestToJson(ImportUrlRequest instance) =>
    <String, dynamic>{
      'url': instance.url,
      'rendered_html': instance.renderedHtml,
      'fetched_url': instance.fetchedUrl,
    };
