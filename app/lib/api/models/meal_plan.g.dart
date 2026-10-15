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
};

Map<String, dynamic> _$RecipeHistoryItemToJson(RecipeHistoryItem instance) =>
    <String, dynamic>{
      'recipe_id': instance.recipeId,
      'title': instance.title,
      'last_cooked_at': instance.lastCookedAt?.toIso8601String(),
      'food_groups': instance.foodGroups,
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
    };

MealPlanRecipe _$MealPlanRecipeFromJson(Map<String, dynamic> json) =>
    MealPlanRecipe(
      recipeId: (json['recipe_id'] as num?)?.toInt(),
      externalId: json['external_id'] as String?,
      title: json['title'] as String,
      reason: json['reason'] as String,
      missingIngredients:
          (json['missing_ingredients'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
    );

MealPlanResponse _$MealPlanResponseFromJson(Map<String, dynamic> json) =>
    MealPlanResponse(
      suggestions: (json['suggestions'] as List<dynamic>)
          .map((e) => MealPlanRecipe.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
