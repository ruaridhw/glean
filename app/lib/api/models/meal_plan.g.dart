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
    };

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
    };

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
        );
        return val;
      },
      fieldKeyMap: const {
        'recipeId': 'recipe_id',
        'externalId': 'external_id',
        'missingIngredients': 'missing_ingredients',
      },
    );

MealPlanResponse _$MealPlanResponseFromJson(Map<String, dynamic> json) =>
    $checkedCreate('MealPlanResponse', json, ($checkedConvert) {
      final val = MealPlanResponse(
        suggestions: $checkedConvert(
          'suggestions',
          (v) => (v as List<dynamic>)
              .map((e) => MealPlanRecipe.fromJson(e as Map<String, dynamic>))
              .toList(),
        ),
      );
      return val;
    });
