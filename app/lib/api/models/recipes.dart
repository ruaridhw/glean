import 'package:json_annotation/json_annotation.dart';

part 'recipes.g.dart';

/// Recipe ingredient as returned inside a [RecipeOut].
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
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

  factory RecipeIngredientOut.fromJson(Map<String, dynamic> json) =>
      _$RecipeIngredientOutFromJson(json);

  final String? apiIngredientId;
  final String canonicalName;
  final double quantity;
  final String unit;
  final String? preparation;
  @JsonKey(defaultValue: false)
  final bool isOptional;
  @JsonKey(defaultValue: <String>[])
  final List<String> substitutions;
}

/// The 7 canonical nutrition fields, mirroring the backend's `NutritionFields` (`backend/src/glean/nutrition.py`).
/// Stored but not shown in the UI yet; modelled so it round-trips without data loss.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
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

  factory NutritionOut.fromJson(Map<String, dynamic> json) =>
      _$NutritionOutFromJson(json);

  @JsonKey(defaultValue: 0.0)
  final double calories;
  @JsonKey(defaultValue: 0.0)
  final double proteinG;
  @JsonKey(defaultValue: 0.0)
  final double carbohydratesG;
  @JsonKey(defaultValue: 0.0)
  final double fatG;
  @JsonKey(defaultValue: 0.0)
  final double fibreG;
  @JsonKey(defaultValue: 0.0)
  final double sugarG;
  @JsonKey(defaultValue: 0.0)
  final double sodiumMg;
}

/// An ordered recipe instruction step.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class InstructionOut {
  const InstructionOut({
    required this.stepNumber,
    required this.phase,
    required this.text,
  });

  factory InstructionOut.fromJson(Map<String, dynamic> json) =>
      _$InstructionOutFromJson(json);

  final int stepNumber;
  final String phase;
  final String text;
}

/// Recipe detail — the response of `GET /recipes/{id}` and
/// `POST /recipes/import-url`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
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

  factory RecipeOut.fromJson(Map<String, dynamic> json) =>
      _$RecipeOutFromJson(json);

  final String externalId;
  final String title;

  /// Shown as tappable attribution for imported recipes.
  final String? sourceUrl;
  final String? cuisine;
  final String? difficulty;
  final int? activeTimeMins;
  final int? totalTimeMins;
  @JsonKey(defaultValue: <String>[])
  final List<String> dietaryFlags;
  @JsonKey(defaultValue: <String>[])
  final List<String> notSuitableFor;
  final int? yieldCount;
  final NutritionOut? nutrition;
  @JsonKey(defaultValue: <InstructionOut>[])
  final List<InstructionOut> instructions;
  @JsonKey(defaultValue: <RecipeIngredientOut>[])
  final List<RecipeIngredientOut> ingredients;
}

/// Compact recipe result inside a [RecipeSearchResponse].
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class RecipeSearchResult {
  const RecipeSearchResult({
    required this.externalId,
    required this.title,
    this.cuisine,
    this.difficulty,
    this.totalTimeMins,
    this.dietaryFlags = const [],
  });

  factory RecipeSearchResult.fromJson(Map<String, dynamic> json) =>
      _$RecipeSearchResultFromJson(json);

  final String externalId;
  final String title;
  final String? cuisine;
  final String? difficulty;
  final int? totalTimeMins;
  @JsonKey(defaultValue: <String>[])
  final List<String> dietaryFlags;
}

/// Response body for `GET /recipes/search`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class RecipeSearchResponse {
  const RecipeSearchResponse({required this.results, required this.total});

  factory RecipeSearchResponse.fromJson(Map<String, dynamic> json) =>
      _$RecipeSearchResponseFromJson(json);

  final List<RecipeSearchResult> results;
  final int total;
}

/// Request body for `POST /recipes/import-url`.
@JsonSerializable(fieldRename: FieldRename.snake, createFactory: false)
class ImportUrlRequest {
  const ImportUrlRequest({
    required this.url,
    this.renderedHtml,
    this.fetchedUrl,
  });

  final String url;
  final String? renderedHtml;
  final String? fetchedUrl;

  Map<String, dynamic> toJson() => _$ImportUrlRequestToJson(this);
}
