// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'meal_plan.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Map<String, dynamic> _$CompressedPantryItemToJson(
  CompressedPantryItem instance,
) => <String, dynamic>{
  'id': instance.id,
  'name': instance.name,
  'quantity': instance.quantity,
  'unit': instance.unit,
  'food_group': instance.foodGroup,
  'urgency_score': instance.urgencyScore,
  'expires_in_days': instance.expiresInDays,
};

Map<String, dynamic> _$RecipeHistoryItemToJson(RecipeHistoryItem instance) =>
    <String, dynamic>{
      'recipe_id': instance.recipeId,
      'title': instance.title,
      'last_cooked_at': instance.lastCookedAt?.toIso8601String(),
      'food_groups': instance.foodGroups,
    };

Map<String, dynamic> _$CookedHistoryItemToJson(CookedHistoryItem instance) =>
    <String, dynamic>{
      'recipe_id': instance.recipeId,
      'title': instance.title,
      'cooked_at': instance.cookedAt.toIso8601String(),
      'rating': instance.rating,
      'note': instance.note,
    };

Map<String, dynamic> _$HumanFeedbackRequestToJson(
  HumanFeedbackRequest instance,
) => <String, dynamic>{'chips': instance.chips, 'note': instance.note};

Map<String, dynamic> _$MealPlanRequestToJson(MealPlanRequest instance) =>
    <String, dynamic>{
      'pantry': instance.pantry.map((e) => e.toJson()).toList(),
      'recipe_history': instance.recipeHistory.map((e) => e.toJson()).toList(),
      'food_group_coverage': instance.foodGroupCoverage,
      'purchase_tolerance': instance.purchaseTolerance,
      'meals_per_week': instance.mealsPerWeek,
      'dietary_flags': instance.dietaryFlags,
      'max_active_time_mins': instance.maxActiveTimeMins,
      'source': instance.source,
      'exclude_external_ids': instance.excludeExternalIds,
      'cooked_history': instance.cookedHistory.map((e) => e.toJson()).toList(),
      'local_date': instance.localDate,
      'human_feedback': instance.humanFeedback?.toJson(),
    };

UsedUpPantryItem _$UsedUpPantryItemFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'UsedUpPantryItem',
      json,
      ($checkedConvert) {
        final val = UsedUpPantryItem(
          name: $checkedConvert('name', (v) => v as String),
          expiresInDays: $checkedConvert(
            'expires_in_days',
            (v) => (v as num?)?.toInt(),
          ),
          goesOff: $checkedConvert('goes_off', (v) => v as String?),
        );
        return val;
      },
      fieldKeyMap: const {
        'expiresInDays': 'expires_in_days',
        'goesOff': 'goes_off',
      },
    );

MealPlanAttributes _$MealPlanAttributesFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'MealPlanAttributes',
      json,
      ($checkedConvert) {
        final val = MealPlanAttributes(
          mainProtein: $checkedConvert('main_protein', (v) => v as String?),
          mainCarb: $checkedConvert('main_carb', (v) => v as String?),
          dishType: $checkedConvert('dish_type', (v) => v as String?),
          activeTimeMins: $checkedConvert(
            'active_time_mins',
            (v) => (v as num?)?.toInt(),
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'mainProtein': 'main_protein',
        'mainCarb': 'main_carb',
        'dishType': 'dish_type',
        'activeTimeMins': 'active_time_mins',
      },
    );

MealPlanRecipe _$MealPlanRecipeFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'MealPlanRecipe',
      json,
      ($checkedConvert) {
        final val = MealPlanRecipe(
          recipeId: $checkedConvert('recipe_id', (v) => (v as num?)?.toInt()),
          externalId: $checkedConvert('external_id', (v) => v as String?),
          title: $checkedConvert('title', (v) => v as String),
          reason: $checkedConvert('reason', (v) => v as String),
          missingIngredients: $checkedConvert(
            'missing_ingredients',
            (v) =>
                (v as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
          ),
          usesUp: $checkedConvert(
            'uses_up',
            (v) =>
                (v as List<dynamic>?)
                    ?.map(
                      (e) =>
                          UsedUpPantryItem.fromJson(e as Map<String, dynamic>),
                    )
                    .toList() ??
                [],
          ),
          reasonKind: $checkedConvert('reason_kind', (v) => v as String?),
          alternative: $checkedConvert(
            'alternative',
            (v) => v == null
                ? null
                : MealPlanRecipe.fromJson(v as Map<String, dynamic>),
          ),
          attributes: $checkedConvert(
            'attributes',
            (v) => v == null
                ? null
                : MealPlanAttributes.fromJson(v as Map<String, dynamic>),
          ),
        );
        return val;
      },
      fieldKeyMap: const {
        'recipeId': 'recipe_id',
        'externalId': 'external_id',
        'missingIngredients': 'missing_ingredients',
        'usesUp': 'uses_up',
        'reasonKind': 'reason_kind',
      },
    );

MealPlanPlannedAlternative _$MealPlanPlannedAlternativeFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'MealPlanPlannedAlternative',
  json,
  ($checkedConvert) {
    final val = MealPlanPlannedAlternative(
      externalId: $checkedConvert('external_id', (v) => v as String),
      alternative: $checkedConvert(
        'alternative',
        (v) => MealPlanRecipe.fromJson(v as Map<String, dynamic>),
      ),
    );
    return val;
  },
  fieldKeyMap: const {'externalId': 'external_id'},
);

MealPlanResponse _$MealPlanResponseFromJson(Map<String, dynamic> json) =>
    $checkedCreate(
      'MealPlanResponse',
      json,
      ($checkedConvert) {
        final val = MealPlanResponse(
          suggestions: $checkedConvert(
            'suggestions',
            (v) => (v as List<dynamic>)
                .map((e) => MealPlanRecipe.fromJson(e as Map<String, dynamic>))
                .toList(),
          ),
          weekSummary: $checkedConvert(
            'week_summary',
            (v) => v as String? ?? '',
          ),
          plannedAlternatives: $checkedConvert(
            'planned_alternatives',
            (v) =>
                (v as List<dynamic>?)
                    ?.map(
                      (e) => MealPlanPlannedAlternative.fromJson(
                        e as Map<String, dynamic>,
                      ),
                    )
                    .toList() ??
                [],
          ),
          degraded: $checkedConvert('degraded', (v) => v as bool? ?? false),
          feedbackNote: $checkedConvert('feedback_note', (v) => v as String?),
        );
        return val;
      },
      fieldKeyMap: const {
        'weekSummary': 'week_summary',
        'plannedAlternatives': 'planned_alternatives',
        'feedbackNote': 'feedback_note',
      },
    );
