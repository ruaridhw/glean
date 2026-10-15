// Read-side shapes for recipes and their ingredients — mirrors `Recipe`,
// `RecipeIngredient` and `Ingredient` in the Expo app's `src/types/index.ts`
// (see git history), decoded from their JSON-text columns, plus `userId`
// (AC-DATA-02).
//
// `instructions` is a typed list of steps rather than the RN app's
// `string[]` — that TS type never matched what `saveRecipe` actually stored
// (`{step_number, phase, text}` objects; see the Expo app's
// `src/db/recipes.ts:70` and `schema.ts`'s default `"[]"`), so porting it
// verbatim would just carry the mismatch into Dart.
class RecipeInstructionStep {
  const RecipeInstructionStep({
    required this.stepNumber,
    required this.phase,
    required this.text,
  });

  final int stepNumber;
  final String phase;
  final String text;

  factory RecipeInstructionStep.fromJson(Map<String, dynamic> json) {
    return RecipeInstructionStep(
      stepNumber: json['step_number'] as int,
      phase: json['phase'] as String,
      text: json['text'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
    'step_number': stepNumber,
    'phase': phase,
    'text': text,
  };
}

class IngredientView {
  const IngredientView({
    required this.id,
    required this.canonicalName,
    required this.apiIngredientId,
    required this.apiName,
    required this.category,
    required this.canonicalUnit,
    required this.isStaple,
  });

  final int id;
  final String canonicalName;
  final String? apiIngredientId;
  final String? apiName;
  final String? category;
  final String? canonicalUnit;
  final bool isStaple;
}

class RecipeIngredientView {
  const RecipeIngredientView({
    required this.id,
    required this.recipeId,
    required this.ingredientId,
    required this.quantity,
    required this.unit,
    required this.preparation,
    required this.isOptional,
    required this.substitutions,
    required this.ingredient,
  });

  final int id;
  final int recipeId;
  final int ingredientId;
  final double quantity;
  final String unit;
  final String? preparation;
  final bool isOptional;
  final List<String> substitutions;
  final IngredientView ingredient;
}

class RecipeView {
  const RecipeView({
    required this.id,
    required this.userId,
    required this.externalId,
    required this.title,
    required this.sourceUrl,
    required this.cuisine,
    required this.difficulty,
    required this.activeTimeMins,
    required this.totalTimeMins,
    required this.notSuitableFor,
    required this.yieldCount,
    required this.nutrition,
    required this.instructions,
    required this.lastCookedAt,
    required this.dietaryFlags,
  });

  final int id;
  final String userId;
  final String? externalId;
  final String title;
  final String? sourceUrl;
  final String? cuisine;
  final String? difficulty;
  final int? activeTimeMins;
  final int? totalTimeMins;
  final List<String> notSuitableFor;
  final int? yieldCount;
  final String? nutrition;
  final List<RecipeInstructionStep> instructions;
  final DateTime? lastCookedAt;
  final List<String> dietaryFlags;

  /// Returns a copy with [flags] attached — used once the dietary-flags
  /// join has been resolved separately (mirrors RN's `attachDietaryFlags`).
  RecipeView withDietaryFlags(List<String> flags) => RecipeView(
    id: id,
    userId: userId,
    externalId: externalId,
    title: title,
    sourceUrl: sourceUrl,
    cuisine: cuisine,
    difficulty: difficulty,
    activeTimeMins: activeTimeMins,
    totalTimeMins: totalTimeMins,
    notSuitableFor: notSuitableFor,
    yieldCount: yieldCount,
    nutrition: nutrition,
    instructions: instructions,
    lastCookedAt: lastCookedAt,
    dietaryFlags: flags,
  );
}
