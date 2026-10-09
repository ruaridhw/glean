/// Top-N urgency-scored pantry item sent to `POST /meal-plan`; the wire shape of the backend's
/// `CompressedPantryItem`. Scoring and compression happen in the data layer.
class CompressedPantryItem {
  const CompressedPantryItem({
    required this.id,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.foodGroup,
    required this.urgencyScore,
  });

  final int id;
  final String name;
  final double quantity;
  final String unit;
  final String foodGroup;
  final double urgencyScore;

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'quantity': quantity,
    'unit': unit,
    'food_group': foodGroup,
    'urgency_score': urgencyScore,
  };
}

/// One saved recipe's cook history, sent to `POST /meal-plan` so the LLM can avoid recent repeats. [foodGroups]
/// (the groups each recipe covers) must be populated, or the backend's "balance food group coverage" rule is inert.
class RecipeHistoryItem {
  const RecipeHistoryItem({
    required this.recipeId,
    required this.title,
    required this.foodGroups,
    this.lastCookedAt,
  });

  final int recipeId;
  final String title;

  /// Null if this recipe has never been cooked.
  final DateTime? lastCookedAt;
  final List<String> foodGroups;

  Map<String, dynamic> toJson() => {
    'recipe_id': recipeId,
    'title': title,
    'last_cooked_at': lastCookedAt?.toIso8601String(),
    'food_groups': foodGroups,
  };
}

/// Request body for `POST /meal-plan`. [foodGroupCoverage] (meals cooked this week per food group) is not
/// defaulted to empty: the caller must compute it.
class MealPlanRequest {
  const MealPlanRequest({
    required this.pantry,
    required this.recipeHistory,
    required this.foodGroupCoverage,
    required this.purchaseTolerance,
    required this.mealsPerWeek,
    required this.dietaryFlags,
    this.maxActiveTimeMins,
    this.source = 'saved',
    this.excludeExternalIds = const [],
  });

  /// Top-N urgency-scored pantry items (staples and zero-quantity items
  /// excluded).
  final List<CompressedPantryItem> pantry;

  final List<RecipeHistoryItem> recipeHistory;

  /// Number of meals cooked this week per food group, e.g.
  /// `{'protein': 2, 'veg': 1}`.
  final Map<String, int> foodGroupCoverage;

  /// 0.0 = only suggest recipes using pantry ingredients; 1.0 = any recipe
  /// regardless of missing items.
  final double purchaseTolerance;

  /// Number of meal-plan slots to fill (may be less than a full week; generation is top-up only).
  final int mealsPerWeek;

  final List<String> dietaryFlags;

  final int? maxActiveTimeMins;

  final String source;
  final List<String> excludeExternalIds;

  Map<String, dynamic> toJson() => {
    'source': source,
    'exclude_external_ids': excludeExternalIds,
    'pantry': pantry.map((item) => item.toJson()).toList(),
    'recipe_history': recipeHistory.map((item) => item.toJson()).toList(),
    'food_group_coverage': foodGroupCoverage,
    'purchase_tolerance': purchaseTolerance,
    'meals_per_week': mealsPerWeek,
    'dietary_flags': dietaryFlags,
    'max_active_time_mins': maxActiveTimeMins,
  };
}

/// A single LLM-suggested recipe returned by `POST /meal-plan`: an ephemeral proposal, persisted only when the
/// user commits it.
class MealPlanRecipe {
  const MealPlanRecipe({
    this.recipeId,
    this.externalId,
    required this.title,
    required this.reason,
    this.missingIngredients = const [],
  });

  factory MealPlanRecipe.fromJson(Map<String, dynamic> json) {
    final rawMissing = json['missing_ingredients'] as List<dynamic>?;
    return MealPlanRecipe(
      recipeId: json['recipe_id'] as int?,
      externalId: json['external_id'] as String?,
      title: json['title'] as String,
      reason: json['reason'] as String,
      missingIngredients:
          rawMissing?.map((i) => i as String).toList() ?? const [],
    );
  }

  final int? recipeId;
  final String? externalId;
  final String title;
  final String reason;
  final List<String> missingIngredients;
}

class MealPlanResponse {
  const MealPlanResponse({required this.suggestions});

  factory MealPlanResponse.fromJson(Map<String, dynamic> json) {
    final rawSuggestions = json['suggestions'] as List<dynamic>;
    return MealPlanResponse(
      suggestions: rawSuggestions
          .map((s) => MealPlanRecipe.fromJson(s as Map<String, dynamic>))
          .toList(),
    );
  }

  final List<MealPlanRecipe> suggestions;
}
