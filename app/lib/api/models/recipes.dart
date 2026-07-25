/// Recipe ingredient as returned inside a [RecipeOut].
class RecipeIngredientOut {
  const RecipeIngredientOut({
    required this.canonicalName,
    required this.quantity,
    required this.unit,
    this.apiIngredientId,
    this.preparation,
    this.isOptional = false,
    this.substitutions = const [],
  });

  factory RecipeIngredientOut.fromJson(Map<String, dynamic> json) {
    final rawSubstitutions = json['substitutions'] as List<dynamic>?;
    return RecipeIngredientOut(
      apiIngredientId: json['api_ingredient_id'] as String?,
      canonicalName: json['canonical_name'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      unit: json['unit'] as String,
      preparation: json['preparation'] as String?,
      isOptional: json['is_optional'] as bool? ?? false,
      substitutions:
          rawSubstitutions?.map((s) => s as String).toList() ?? const [],
    );
  }

  final String? apiIngredientId;
  final String canonicalName;
  final double quantity;
  final String unit;
  final String? preparation;
  final bool isOptional;
  final List<String> substitutions;
}

/// The 7 canonical nutrition fields, mirroring the backend's shared
/// `NutritionFields` (`backend/src/glean/nutrition.py`). Stored but not
/// shown in the UI yet (FLUTTER_MIGRATION.md §1 — out of scope for this
/// port); modelled here so it round-trips without data loss.
class NutritionOut {
  const NutritionOut({
    this.calories = 0,
    this.proteinG = 0,
    this.carbohydratesG = 0,
    this.fatG = 0,
    this.fibreG = 0,
    this.sugarG = 0,
    this.sodiumMg = 0,
  });

  factory NutritionOut.fromJson(Map<String, dynamic> json) {
    double field(String key) => (json[key] as num? ?? 0).toDouble();
    return NutritionOut(
      calories: field('calories'),
      proteinG: field('protein_g'),
      carbohydratesG: field('carbohydrates_g'),
      fatG: field('fat_g'),
      fibreG: field('fibre_g'),
      sugarG: field('sugar_g'),
      sodiumMg: field('sodium_mg'),
    );
  }

  final double calories;
  final double proteinG;
  final double carbohydratesG;
  final double fatG;
  final double fibreG;
  final double sugarG;
  final double sodiumMg;
}

/// An ordered recipe instruction step.
class InstructionOut {
  const InstructionOut({
    required this.stepNumber,
    required this.phase,
    required this.text,
  });

  factory InstructionOut.fromJson(Map<String, dynamic> json) {
    return InstructionOut(
      stepNumber: json['step_number'] as int,
      phase: json['phase'] as String,
      text: json['text'] as String,
    );
  }

  final int stepNumber;
  final String phase;
  final String text;
}

/// Recipe detail — the response of `GET /recipes/{id}` and
/// `POST /recipes/import-url`.
class RecipeOut {
  const RecipeOut({
    required this.externalId,
    required this.title,
    this.sourceUrl,
    this.cuisine,
    this.difficulty,
    this.activeTimeMins,
    this.totalTimeMins,
    this.dietaryFlags = const [],
    this.notSuitableFor = const [],
    this.yieldCount,
    this.nutrition,
    this.instructions = const [],
    this.ingredients = const [],
  });

  factory RecipeOut.fromJson(Map<String, dynamic> json) {
    final rawNutrition = json['nutrition'] as Map<String, dynamic>?;
    final rawInstructions = json['instructions'] as List<dynamic>?;
    final rawIngredients = json['ingredients'] as List<dynamic>?;
    final rawDietaryFlags = json['dietary_flags'] as List<dynamic>?;
    final rawNotSuitableFor = json['not_suitable_for'] as List<dynamic>?;
    return RecipeOut(
      externalId: json['external_id'] as String,
      title: json['title'] as String,
      sourceUrl: json['source_url'] as String?,
      cuisine: json['cuisine'] as String?,
      difficulty: json['difficulty'] as String?,
      activeTimeMins: json['active_time_mins'] as int?,
      totalTimeMins: json['total_time_mins'] as int?,
      dietaryFlags:
          rawDietaryFlags?.map((f) => f as String).toList() ?? const [],
      // AC-MEAL-04: surfaced prominently on the recipe detail — stored and
      // displayed nowhere in the RN app.
      notSuitableFor:
          rawNotSuitableFor?.map((f) => f as String).toList() ?? const [],
      yieldCount: json['yield_count'] as int?,
      nutrition: rawNutrition == null
          ? null
          : NutritionOut.fromJson(rawNutrition),
      instructions:
          rawInstructions
              ?.map((i) => InstructionOut.fromJson(i as Map<String, dynamic>))
              .toList() ??
          const [],
      ingredients:
          rawIngredients
              ?.map(
                (i) => RecipeIngredientOut.fromJson(i as Map<String, dynamic>),
              )
              .toList() ??
          const [],
    );
  }

  final String externalId;
  final String title;

  /// AC-MEAL-05: surfaced as tappable attribution for imported recipes.
  final String? sourceUrl;
  final String? cuisine;
  final String? difficulty;
  final int? activeTimeMins;
  final int? totalTimeMins;
  final List<String> dietaryFlags;
  final List<String> notSuitableFor;
  final int? yieldCount;
  final NutritionOut? nutrition;
  final List<InstructionOut> instructions;
  final List<RecipeIngredientOut> ingredients;
}

/// Compact recipe result inside a [RecipeSearchResponse].
class RecipeSearchResult {
  const RecipeSearchResult({
    required this.externalId,
    required this.title,
    this.cuisine,
    this.difficulty,
    this.totalTimeMins,
    this.dietaryFlags = const [],
  });

  factory RecipeSearchResult.fromJson(Map<String, dynamic> json) {
    final rawDietaryFlags = json['dietary_flags'] as List<dynamic>?;
    return RecipeSearchResult(
      externalId: json['external_id'] as String,
      title: json['title'] as String,
      cuisine: json['cuisine'] as String?,
      difficulty: json['difficulty'] as String?,
      totalTimeMins: json['total_time_mins'] as int?,
      dietaryFlags:
          rawDietaryFlags?.map((f) => f as String).toList() ?? const [],
    );
  }

  final String externalId;
  final String title;
  final String? cuisine;
  final String? difficulty;
  final int? totalTimeMins;
  final List<String> dietaryFlags;
}

/// Response body for `GET /recipes/search`.
class RecipeSearchResponse {
  const RecipeSearchResponse({required this.results, required this.total});

  factory RecipeSearchResponse.fromJson(Map<String, dynamic> json) {
    final rawResults = json['results'] as List<dynamic>;
    return RecipeSearchResponse(
      results: rawResults
          .map((r) => RecipeSearchResult.fromJson(r as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
    );
  }

  final List<RecipeSearchResult> results;
  final int total;
}

/// Request body for `POST /recipes/import-url`.
class ImportUrlRequest {
  const ImportUrlRequest({
    required this.url,
    this.renderedHtml,
    this.fetchedUrl,
  });

  final String url;
  final String? renderedHtml;
  final String? fetchedUrl;

  Map<String, dynamic> toJson() => {
    'url': url,
    'rendered_html': renderedHtml,
    'fetched_url': fetchedUrl,
  };
}
