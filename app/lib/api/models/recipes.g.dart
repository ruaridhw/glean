// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'recipes.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

RecipeIngredientOut _$RecipeIngredientOutFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'RecipeIngredientOut',
      json,
      ($checkedConvert) {
        final val = RecipeIngredientOut(
          canonicalName: $checkedConvert('canonical_name', (v) => v as String),
          quantity: $checkedConvert('quantity', (v) => (v as num).toDouble()),
          unit: $checkedConvert('unit', (v) => v as String),
          apiIngredientId: $checkedConvert(
            'api_ingredient_id',
            (v) => v as String?,
          ),
          preparation: $checkedConvert('preparation', (v) => v as String?),
          isOptional: $checkedConvert(
            'is_optional',
            (v) => v as bool? ?? false,
          ),
          substitutions: $checkedConvert(
            'substitutions',
            (v) =>
                (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'canonicalName': 'canonical_name',
        'apiIngredientId': 'api_ingredient_id',
        'isOptional': 'is_optional',
      },
    );

NutritionOut _$NutritionOutFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'NutritionOut',
  json,
  ($checkedConvert) {
    final val = NutritionOut(
      calories: $checkedConvert(
        'calories',
        (v) => (v as num?)?.toDouble() ?? 0.0,
      ),
      proteinG: $checkedConvert(
        'protein_g',
        (v) => (v as num?)?.toDouble() ?? 0.0,
      ),
      carbohydratesG: $checkedConvert(
        'carbohydrates_g',
        (v) => (v as num?)?.toDouble() ?? 0.0,
      ),
      fatG: $checkedConvert('fat_g', (v) => (v as num?)?.toDouble() ?? 0.0),
      fibreG: $checkedConvert('fibre_g', (v) => (v as num?)?.toDouble() ?? 0.0),
      sugarG: $checkedConvert('sugar_g', (v) => (v as num?)?.toDouble() ?? 0.0),
      sodiumMg: $checkedConvert(
        'sodium_mg',
        (v) => (v as num?)?.toDouble() ?? 0.0,
      ),
    );
    return val;
  },
  fieldKeyMap: const {
    'proteinG': 'protein_g',
    'carbohydratesG': 'carbohydrates_g',
    'fatG': 'fat_g',
    'fibreG': 'fibre_g',
    'sugarG': 'sugar_g',
    'sodiumMg': 'sodium_mg',
  },
);

InstructionOut _$InstructionOutFromJson(Map<String, dynamic> json) =>
    $checkedCreate('InstructionOut', json, ($checkedConvert) {
      final val = InstructionOut(
        stepNumber: $checkedConvert('step_number', (v) => (v as num).toInt()),
        phase: $checkedConvert('phase', (v) => v as String),
        text: $checkedConvert('text', (v) => v as String),
      );
      return val;
    }, fieldKeyMap: const {'stepNumber': 'step_number'});

RecipeOut _$RecipeOutFromJson(Map<String, dynamic> json) => $checkedCreate(
  'RecipeOut',
  json,
  ($checkedConvert) {
    final val = RecipeOut(
      externalId: $checkedConvert('external_id', (v) => v as String),
      title: $checkedConvert('title', (v) => v as String),
      sourceUrl: $checkedConvert('source_url', (v) => v as String?),
      cuisine: $checkedConvert('cuisine', (v) => v as String?),
      difficulty: $checkedConvert('difficulty', (v) => v as String?),
      activeTimeMins: $checkedConvert(
        'active_time_mins',
        (v) => (v as num?)?.toInt(),
      ),
      totalTimeMins: $checkedConvert(
        'total_time_mins',
        (v) => (v as num?)?.toInt(),
      ),
      dietaryFlags: $checkedConvert(
        'dietary_flags',
        (v) => (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      ),
      notSuitableFor: $checkedConvert(
        'not_suitable_for',
        (v) => (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      ),
      yieldCount: $checkedConvert('yield_count', (v) => (v as num?)?.toInt()),
      nutrition: $checkedConvert(
        'nutrition',
        (v) =>
            v == null ? null : NutritionOut.fromJson(v as Map<String, dynamic>),
      ),
      instructions: $checkedConvert(
        'instructions',
        (v) =>
            (v as List<dynamic>?)
                ?.map((e) => InstructionOut.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
      ),
      ingredients: $checkedConvert(
        'ingredients',
        (v) =>
            (v as List<dynamic>?)
                ?.map(
                  (e) =>
                      RecipeIngredientOut.fromJson(e as Map<String, dynamic>),
                )
                .toList() ??
            [],
      ),
    );
    return val;
  },
  fieldKeyMap: const {
    'externalId': 'external_id',
    'sourceUrl': 'source_url',
    'activeTimeMins': 'active_time_mins',
    'totalTimeMins': 'total_time_mins',
    'dietaryFlags': 'dietary_flags',
    'notSuitableFor': 'not_suitable_for',
    'yieldCount': 'yield_count',
  },
);

RecipeSearchResult _$RecipeSearchResultFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'RecipeSearchResult',
      json,
      ($checkedConvert) {
        final val = RecipeSearchResult(
          externalId: $checkedConvert('external_id', (v) => v as String),
          title: $checkedConvert('title', (v) => v as String),
          cuisine: $checkedConvert('cuisine', (v) => v as String?),
          difficulty: $checkedConvert('difficulty', (v) => v as String?),
          totalTimeMins: $checkedConvert(
            'total_time_mins',
            (v) => (v as num?)?.toInt(),
          ),
          dietaryFlags: $checkedConvert(
            'dietary_flags',
            (v) =>
                (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'externalId': 'external_id',
        'totalTimeMins': 'total_time_mins',
        'dietaryFlags': 'dietary_flags',
      },
    );

RecipeSearchResponse _$RecipeSearchResponseFromJson(
  Map<String, dynamic> json,
) => $checkedCreate('RecipeSearchResponse', json, ($checkedConvert) {
  final val = RecipeSearchResponse(
    results: $checkedConvert(
      'results',
      (v) => (v as List<dynamic>)
          .map((e) => RecipeSearchResult.fromJson(e as Map<String, dynamic>))
          .toList(),
    ),
    total: $checkedConvert('total', (v) => (v as num).toInt()),
  );
  return val;
});

Map<String, dynamic> _$ImportUrlRequestToJson(ImportUrlRequest instance) =>
    <String, dynamic>{
      'url': instance.url,
      'rendered_html': instance.renderedHtml,
      'fetched_url': instance.fetchedUrl,
    };
