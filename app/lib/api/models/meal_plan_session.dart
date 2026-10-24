import 'package:json_annotation/json_annotation.dart';

import 'meal_plan.dart';

part 'meal_plan_session.g.dart';

/// Where a Generate session has got to. V1 renders the spinner for every non-terminal status and only reacts to
/// [done] and [failed]; progress lines and [waitingForUser] arrive with V3.
///
/// A status this build does not know parses as [unknown] and is never terminal, so an app meeting a newer
/// backend keeps polling rather than inventing an outcome.
enum MealPlanSessionStatus {
  @JsonValue('queued')
  queued,
  @JsonValue('running')
  running,
  @JsonValue('waiting_for_user')
  waitingForUser,
  @JsonValue('done')
  done,
  @JsonValue('failed')
  failed,
  @JsonValue('unknown')
  unknown,
}

/// The `202` body from `POST /meal-plan/sessions`: the id to poll. The id is held in memory for the life of one
/// Generate attempt only, so an app killed mid-run simply starts a new session next time.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanSessionCreated {
  const MealPlanSessionCreated({required this.sessionId});

  factory MealPlanSessionCreated.fromJson(Map<String, dynamic> json) =>
      _$MealPlanSessionCreatedFromJson(json);

  final String sessionId;
}

/// The typed failure a session ends with. [code] is internal: the app maps it through the approved catalogue
/// (`lib/features/plan/generate_failure.dart`) and never shows it. [retryAfterMinutes] is set for `rate_limited`.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanSessionError {
  const MealPlanSessionError({required this.code, this.retryAfterMinutes});

  factory MealPlanSessionError.fromJson(Map<String, dynamic> json) =>
      _$MealPlanSessionErrorFromJson(json);

  final String code;
  final int? retryAfterMinutes;
}

/// One poll of `GET /meal-plan/sessions/{id}?after=<cursor>`. [progress] holds the lines written since the
/// cursor that was sent; [nextCursor] is what the next poll sends back. [result] is today's meal plan on [done],
/// and [error] is the typed failure on [failed]; both are null while the session runs.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanSessionUpdate {
  const MealPlanSessionUpdate({
    required this.status,
    this.progress = const <String>[],
    this.nextCursor = 0,
    this.result,
    this.error,
    this.sessionId,
    this.updatedAt,
  });

  factory MealPlanSessionUpdate.fromJson(Map<String, dynamic> json) =>
      _$MealPlanSessionUpdateFromJson(json);

  @JsonKey(unknownEnumValue: MealPlanSessionStatus.unknown)
  final MealPlanSessionStatus status;
  final List<String> progress;

  /// The cursor the next poll sends as `after`, so progress lines are not repeated.
  final int nextCursor;
  final MealPlanResponse? result;
  final MealPlanSessionError? error;

  /// Echoed by the backend for logs; the app already knows the id it is polling.
  final String? sessionId;

  /// When the session last changed. Observability only: V1 renders whatever status comes back and has no
  /// staleness logic.
  final DateTime? updatedAt;

  /// `done` and `failed` are the only outcomes that end a Generate attempt; everything else keeps polling.
  bool get isTerminal =>
      status == MealPlanSessionStatus.done ||
      status == MealPlanSessionStatus.failed;
}
