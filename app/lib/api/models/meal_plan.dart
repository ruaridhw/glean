import 'package:json_annotation/json_annotation.dart';

part 'meal_plan.g.dart';

/// Top-N urgency-scored pantry item sent to `POST /meal-plan`; the wire shape of the backend's
/// `CompressedPantryItem`. Scoring and compression happen in the data layer.
@JsonSerializable(fieldRename: FieldRename.snake, createFactory: false)
class CompressedPantryItem {
  const CompressedPantryItem({
    required this.id,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.foodGroup,
    required this.urgencyScore,
    this.expiresInDays,
  });

  final int id;
  final String name;
  final double quantity;
  final String unit;
  final String foodGroup;
  final double urgencyScore;

  /// Whole calendar days until [expiryDate], or null when the item has no expiry date. The backend
  /// cannot recover this from [urgencyScore], and it uses it to name the item in a meal's reason.
  final int? expiresInDays;

  Map<String, dynamic> toJson() => _$CompressedPantryItemToJson(this);
}

/// One saved recipe's cook history, sent to `POST /meal-plan` so the LLM can avoid recent repeats. [foodGroups]
/// (the groups each recipe covers) must be populated, or the backend's "balance food group coverage" rule is inert.
@JsonSerializable(fieldRename: FieldRename.snake, createFactory: false)
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

  Map<String, dynamic> toJson() => _$RecipeHistoryItemToJson(this);
}

/// One meal the household actually cooked, sent to `POST /meal-plan` so corpus generation can leave it out of
/// the week while it is too recent to repeat, and never offer a recipe they gave a thumbs down. The wire shape
/// of the backend's `CookedHistoryItem`.
@JsonSerializable(fieldRename: FieldRename.snake, createFactory: false)
class CookedHistoryItem {
  const CookedHistoryItem({
    required this.title,
    required this.cookedAt,
    this.recipeId,
    this.rating,
    this.note,
  });

  /// Corpus recipe id, kept on the plan entry as `externalIdSnapshot`; null for a meal cooked before the app
  /// stored that snapshot, so the title is all the backend can match on.
  final String? recipeId;
  final String title;
  final DateTime cookedAt;

  /// 'up' or 'down' (`MealThumb.dbValue`), or null when the meal was not rated. The app writes the thumb;
  /// the backend reads only the latest one per recipe.
  final String? rating;

  /// The comment saved with [rating], bounded by `maxRatingNoteLength` code points (the phone counts the
  /// same unit, so a saved note always passes the backend's validation). The backend never puts it in a
  /// prompt yet: that is the feedback screen's job, and it does not exist.
  final String? note;

  Map<String, dynamic> toJson() => _$CookedHistoryItemToJson(this);
}

/// Request body for `POST /meal-plan`. [foodGroupCoverage] (meals cooked this week per food group) is not
/// defaulted to empty: the caller must compute it.
@JsonSerializable(
  fieldRename: FieldRename.snake,
  createFactory: false,
  explicitToJson: true,
)
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
    this.cookedHistory = const [],
    this.localDate,
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

  /// Meals cooked in the last twelve weeks, so the plan can avoid repeating them.
  final List<CookedHistoryItem> cookedHistory;

  /// The phone's local calendar date (`YYYY-MM-DD`), the date [pantry]'s `expiresInDays` was measured
  /// from. The backend dates a going-off item in the household's calendar, not the server's UTC one.
  final String? localDate;

  Map<String, dynamic> toJson() => _$MealPlanRequestToJson(this);
}

/// One urgent pantry item a planned meal uses up. The server writes this alongside the reason so a later
/// screen can render the expiry without parsing prose.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class UsedUpPantryItem {
  const UsedUpPantryItem({
    required this.name,
    this.expiresInDays,
    this.goesOff,
  });

  factory UsedUpPantryItem.fromJson(Map<String, dynamic> json) =>
      _$UsedUpPantryItemFromJson(json);

  final String name;

  /// Whole days until the item goes off; null when the server did not know.
  final int? expiresInDays;

  /// Weekday the item goes off in the household's calendar, e.g. `Thu`; null when unknown.
  final String? goesOff;
}

/// A single LLM-suggested recipe returned by `POST /meal-plan`: an ephemeral proposal, persisted only when the
/// user commits it.
///
/// [reasonKind] and [alternative] are additive session-contract fields: an older backend omits them, so both
/// parse as null and the app renders exactly as it did before they existed.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanRecipe {
  const MealPlanRecipe({
    this.recipeId,
    this.externalId,
    required this.title,
    required this.reason,
    this.missingIngredients = const [],
    this.usesUp = const [],
    this.reasonKind,
    this.alternative,
  });

  factory MealPlanRecipe.fromJson(Map<String, dynamic> json) =>
      _$MealPlanRecipeFromJson(json);

  final int? recipeId;
  final String? externalId;
  final String title;
  final String reason;
  @JsonKey(defaultValue: <String>[])
  final List<String> missingIngredients;

  /// Urgent pantry items this meal uses up, soonest to go off first. The reason already names them; the screen
  /// does not invent separate copy for them.
  @JsonKey(defaultValue: <UsedUpPantryItem>[])
  final List<UsedUpPantryItem> usesUp;

  /// Why the planner picked this meal, as a machine-readable tag. V3 shows the reason text; the tag is kept so a
  /// later screen can group or explain reasons without re-parsing prose.
  final String? reasonKind;

  /// One diet-safe alternative from the same candidate pool, or null when the server offered none. Swapping is
  /// local and instant: this is a suggestion, not a saved recipe.
  final MealPlanRecipe? alternative;
}

/// A meal already in the week that the planner also offered an alternative for, matched by the corpus id the
/// planned entry snapshots. Generation never replaces a planned meal on its own (ADR 0020); this only makes the
/// user's own swap possible.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanPlannedAlternative {
  const MealPlanPlannedAlternative({
    required this.externalId,
    required this.alternative,
  });

  factory MealPlanPlannedAlternative.fromJson(Map<String, dynamic> json) =>
      _$MealPlanPlannedAlternativeFromJson(json);

  /// Corpus id of the meal already in the week, as snapshotted on its plan entry.
  final String externalId;
  final MealPlanRecipe alternative;
}

/// The proposal a session's `done` status carries. The sync `POST /meal-plan` returns the same shape.
///
/// Every field beyond [suggestions] is additive: old responses parse with an empty summary, no planned
/// alternatives and `degraded: false`, and the proposal screen renders them unchanged.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanResponse {
  const MealPlanResponse({
    required this.suggestions,
    this.weekSummary = '',
    this.plannedAlternatives = const <MealPlanPlannedAlternative>[],
    this.degraded = false,
  });

  factory MealPlanResponse.fromJson(Map<String, dynamic> json) =>
      _$MealPlanResponseFromJson(json);

  final List<MealPlanRecipe> suggestions;

  /// One line describing the week. Empty only when an old backend did not send one; the screen then omits the
  /// summary card rather than inventing copy.
  @JsonKey(defaultValue: '')
  final String weekSummary;

  /// Alternatives for meals already in the week, for the user's own swap. May be empty.
  @JsonKey(defaultValue: <MealPlanPlannedAlternative>[])
  final List<MealPlanPlannedAlternative> plannedAlternatives;

  /// True when finalise fell back to template reasons. The UI must not treat it differently, so nothing in the
  /// app branches on it; it stays parsed for diagnostics and evals.
  @JsonKey(defaultValue: false)
  final bool degraded;
}
