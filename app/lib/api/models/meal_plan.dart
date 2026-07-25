/// Top-N urgency-scored pantry item sent to `POST /meal-plan`. Building the
/// urgency score and top-N compression is the DATA module's job (ported
/// from `mobile/src/meal-plan/compress.ts`); this model is just the wire
/// shape the backend's `CompressedPantryItem` schema expects.
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

/// One saved recipe's cook history, sent to `POST /meal-plan` so the LLM can
/// avoid recent repeats and balance food-group coverage.
///
/// [foodGroups] is part of AC-PLAN-08: the RN client hardcoded
/// `food_group_coverage` empty everywhere, which made the backend's
/// "balance food group coverage" prompt rule permanently inert
/// (FLUTTER_MIGRATION.md §6). This field — the food groups each recipe
/// covers — is what the caller populates to make that rule live again.
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

/// Request body for `POST /meal-plan`.
///
/// [foodGroupCoverage] is the other half of AC-PLAN-08 alongside
/// [RecipeHistoryItem.foodGroups] — the number of meals cooked this week
/// per food group. The caller (DATA/features) must compute and pass a real
/// map here; this model does not default it to empty, unlike the RN client.
class MealPlanRequest {
  const MealPlanRequest({
    required this.pantry,
    required this.recipeHistory,
    required this.foodGroupCoverage,
    required this.purchaseTolerance,
    required this.mealsPerWeek,
    required this.dietaryFlags,
    this.maxActiveTimeMins,
  });

  /// Top-N urgency-scored pantry items (staples and zero-quantity items
  /// excluded).
  final List<CompressedPantryItem> pantry;

  /// All saved recipes with their last-cooked timestamps.
  final List<RecipeHistoryItem> recipeHistory;

  /// Number of meals cooked this week per food group, e.g.
  /// `{'protein': 2, 'veg': 1}`.
  final Map<String, int> foodGroupCoverage;

  /// 0.0 = only suggest recipes using pantry ingredients; 1.0 = any recipe
  /// regardless of missing items.
  final double purchaseTolerance;

  /// Number of meal-plan slots to fill (may be less than a full week if the
  /// plan is partially filled — generation is top-up only, AC-PLAN-06).
  final int mealsPerWeek;

  final List<String> dietaryFlags;

  /// Null means no limit.
  final int? maxActiveTimeMins;

  Map<String, dynamic> toJson() => {
    'pantry': pantry.map((item) => item.toJson()).toList(),
    'recipe_history': recipeHistory.map((item) => item.toJson()).toList(),
    'food_group_coverage': foodGroupCoverage,
    'purchase_tolerance': purchaseTolerance,
    'meals_per_week': mealsPerWeek,
    'dietary_flags': dietaryFlags,
    'max_active_time_mins': maxActiveTimeMins,
  };
}

/// A single LLM-suggested recipe returned by `POST /meal-plan`. This is an
/// ephemeral proposal (AC-DATA-06) — nothing is persisted until the user
/// reviews and commits it via a DATA mutation.
class MealPlanRecipe {
  const MealPlanRecipe({
    required this.recipeId,
    required this.title,
    required this.reason,
    this.missingIngredients = const [],
  });

  factory MealPlanRecipe.fromJson(Map<String, dynamic> json) {
    final rawMissing = json['missing_ingredients'] as List<dynamic>?;
    return MealPlanRecipe(
      recipeId: json['recipe_id'] as int,
      title: json['title'] as String,
      reason: json['reason'] as String,
      missingIngredients:
          rawMissing?.map((i) => i as String).toList() ?? const [],
    );
  }

  final int recipeId;
  final String title;
  final String reason;
  final List<String> missingIngredients;
}

/// Response body for `POST /meal-plan`.
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
