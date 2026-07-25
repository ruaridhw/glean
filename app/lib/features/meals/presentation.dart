/// Ported from `mobile/src/meals/presentation.ts` — pure, unit-testable
/// formatting helpers (FLUTTER_MIGRATION.md's "Highest-value logic to port
/// faithfully" table).
///
/// `parseInstructionSteps` has no Dart equivalent to port: it existed in RN
/// only to decode a JSON-text `instructions` column into typed steps at the
/// UI layer. Here that decode already happened once, at the data/API
/// boundary — `RecipeView.instructions` (drift) and `RecipeOut.instructions`
/// (the API model) both arrive as typed `List<...Step>` already, so there is
/// no JSON left for a screen to parse.
library;

import 'package:flutter/material.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/data/models/recipe_view.dart';

/// One icon+label pair for a recipe's meta row (time / servings /
/// difficulty) — ported 1:1 from RN's `getRecipeMeta`. Icons are built-in
/// Material `_rounded` glyphs (AC-DS-06), not the RN app's Ionicons names.
class RecipeMetaItem {
  const RecipeMetaItem({required this.icon, required this.label});

  final IconData icon;
  final String label;
}

List<RecipeMetaItem> getRecipeMeta({
  required int? totalTimeMins,
  required int? yieldCount,
  required String? difficulty,
}) {
  return <RecipeMetaItem>[
    if (totalTimeMins != null)
      RecipeMetaItem(
        icon: Icons.access_time_rounded,
        label: '$totalTimeMins min',
      ),
    if (yieldCount != null)
      RecipeMetaItem(
        icon: Icons.people_outline_rounded,
        label: '$yieldCount servings',
      ),
    if (difficulty != null && difficulty.isNotEmpty)
      RecipeMetaItem(icon: Icons.speed_rounded, label: difficulty),
  ];
}

/// Cuisine + dietary flags as a flat tag list — ported 1:1 from RN's
/// `getRecipeTags`.
List<String> getRecipeTags({
  required String? cuisine,
  required List<String> dietaryFlags,
}) {
  return <String>[
    if (cuisine != null && cuisine.isNotEmpty) cuisine,
    ...dietaryFlags,
  ];
}

/// A flattened ingredient line, independent of whether it came from the
/// saved-recipe library (`RecipeIngredientView`, nested under `.ingredient`)
/// or an ephemeral API proposal (`RecipeIngredientOut`, already flat) — one
/// formatter serves both display sources (see [RecipeDetailData]).
class IngredientLine {
  const IngredientLine({
    required this.canonicalName,
    required this.quantity,
    required this.unit,
    this.preparation,
    this.isOptional = false,
    this.inPantry,
  });

  final String canonicalName;
  final double quantity;
  final String unit;
  final String? preparation;
  final bool isOptional;

  /// null = pantry state unknown — an unsaved preview has no resolved
  /// ingredient identity to match against the pantry yet, so the badge is
  /// hidden rather than guessed (mirrors RN's graceful degrade for a failed
  /// pantry lookup, `[id].tsx`'s `pantryIds: Set<number> | null`).
  final bool? inPantry;
}

const Set<String> _compactUnits = <String>{
  'g',
  'kg',
  'ml',
  'l',
  'tsp',
  'tbsp',
  'cm',
};

/// Ported 1:1 from RN's `formatRecipeIngredient`.
String formatIngredientLine(IngredientLine ingredient) {
  final String preparation = ingredient.preparation != null
      ? ', ${ingredient.preparation}'
      : '';
  final String optional = ingredient.isOptional ? ' (optional)' : '';
  final String base = '${ingredient.canonicalName}$preparation$optional'.trim();

  if (ingredient.quantity == 0 && ingredient.unit.isEmpty) {
    return base;
  }
  final String quantity = _formatQuantity(ingredient.quantity);
  if (ingredient.unit == 'pcs') {
    return '${quantity}x $base';
  }
  if (_compactUnits.contains(ingredient.unit)) {
    return '$quantity${ingredient.unit} $base';
  }
  return '$quantity ${ingredient.unit} $base';
}

String _formatQuantity(double quantity) {
  return quantity == quantity.roundToDouble()
      ? quantity.toStringAsFixed(0)
      : quantity.toString();
}

/// An ordered instruction step, flattened from either `RecipeInstructionStep`
/// (saved) or `InstructionOut` (API preview) — the UI never needs `phase`.
class InstructionLine {
  const InstructionLine({required this.number, required this.text});

  final int number;
  final String text;
}

/// Presentation-ready recipe detail: the single shape `RecipeDetailView`
/// renders, whichever of the saved library (`RecipeView`) or an ephemeral
/// API proposal (`RecipeOut`) it was built from.
class RecipeDetailData {
  const RecipeDetailData({
    required this.title,
    required this.tags,
    required this.notSuitableFor,
    required this.sourceUrl,
    required this.totalTimeMins,
    required this.activeTimeMins,
    required this.yieldCount,
    required this.ingredients,
    required this.instructions,
  });

  final String title;
  final List<String> tags;

  /// AC-MEAL-04: surfaced prominently — stored and shown nowhere in the RN
  /// app.
  final List<String> notSuitableFor;

  /// AC-MEAL-05: surfaced as tappable attribution for imported recipes.
  final String? sourceUrl;
  final int? totalTimeMins;
  final int? activeTimeMins;
  final int? yieldCount;
  final List<IngredientLine> ingredients;
  final List<InstructionLine> instructions;

  /// Built from a saved-library recipe. [pantryIngredientIds] is `null`
  /// while the pantry lookup hasn't resolved (or failed) — every ingredient
  /// line's `inPantry` degrades to `null` in that case, matching RN's
  /// graceful degrade rather than guessing "to buy".
  factory RecipeDetailData.fromSaved({
    required RecipeView recipe,
    required List<RecipeIngredientView> ingredients,
    required Set<int>? pantryIngredientIds,
  }) {
    return RecipeDetailData(
      title: recipe.title,
      tags: getRecipeTags(
        cuisine: recipe.cuisine,
        dietaryFlags: recipe.dietaryFlags,
      ),
      notSuitableFor: recipe.notSuitableFor,
      sourceUrl: recipe.sourceUrl,
      totalTimeMins: recipe.totalTimeMins,
      activeTimeMins: recipe.activeTimeMins,
      yieldCount: recipe.yieldCount,
      ingredients: <IngredientLine>[
        for (final RecipeIngredientView ing in ingredients)
          IngredientLine(
            canonicalName: ing.ingredient.canonicalName,
            quantity: ing.quantity,
            unit: ing.unit,
            preparation: ing.preparation,
            isOptional: ing.isOptional,
            inPantry: pantryIngredientIds?.contains(ing.ingredientId),
          ),
      ],
      instructions: <InstructionLine>[
        for (final RecipeInstructionStep step in recipe.instructions)
          InstructionLine(number: step.stepNumber, text: step.text),
      ],
    );
  }

  /// Built from an ephemeral, not-yet-saved API proposal. Ingredients have
  /// no resolved identity yet, so `inPantry` is always `null` here.
  factory RecipeDetailData.fromApi(RecipeOut recipe) {
    return RecipeDetailData(
      title: recipe.title,
      tags: getRecipeTags(
        cuisine: recipe.cuisine,
        dietaryFlags: recipe.dietaryFlags,
      ),
      notSuitableFor: recipe.notSuitableFor,
      sourceUrl: recipe.sourceUrl,
      totalTimeMins: recipe.totalTimeMins,
      activeTimeMins: recipe.activeTimeMins,
      yieldCount: recipe.yieldCount,
      ingredients: <IngredientLine>[
        for (final RecipeIngredientOut ing in recipe.ingredients)
          IngredientLine(
            canonicalName: ing.canonicalName,
            quantity: ing.quantity,
            unit: ing.unit,
            preparation: ing.preparation,
            isOptional: ing.isOptional,
          ),
      ],
      instructions: <InstructionLine>[
        for (final InstructionOut step in recipe.instructions)
          InstructionLine(number: step.stepNumber, text: step.text),
      ],
    );
  }
}

/// Ported from RN's `getRecipeSearchErrorMessage` (`search.tsx`): a 5xx (or
/// other server-side rejection) reads differently from "can't reach the
/// server at all" — [GleanApiClient] already gives us that distinction as a
/// typed exception, where RN had to sniff a plain `status` field.
String describeRecipeSearchError(Object error) {
  if (error is ApiServerException) {
    return 'Search failed because the server returned an error.';
  }
  return 'Search failed. Check your connection and try again.';
}
