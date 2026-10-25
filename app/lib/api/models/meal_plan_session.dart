import 'package:json_annotation/json_annotation.dart';

import 'meal_plan.dart';

part 'meal_plan_session.g.dart';

/// Where a Generate session has got to. [waitingForUser] keeps the proposal screen in its working state: the
/// question step is V11. [cancelled] is terminal and is what the server reports after the app's DELETE.
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
  @JsonValue('cancelled')
  cancelled,
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

/// Where one swap (V10) has got to. Only [pending] is unfinished. A state this build does not know is [unknown]
/// and is treated like a failure of that swap, never as a replacement.
enum MealPlanSwapState {
  @JsonValue('pending')
  pending,
  @JsonValue('done')
  done,
  @JsonValue('no_replacement')
  noReplacement,
  @JsonValue('failed')
  failed,
  @JsonValue('unknown')
  unknown,
}

/// What became of a swap note: none was sent, it was used, or the injection screen dropped it ("Couldn't use
/// that note"; the swap still ran without it).
enum MealPlanSwapNote {
  @JsonValue('none')
  none,
  @JsonValue('used')
  used,
  @JsonValue('dropped')
  dropped,
  @JsonValue('unknown')
  unknown,
}

/// The body of `POST /meal-plan/sessions/{id}/messages`: one union, discriminated on `type`. A swap (V10) asks
/// for another meal in one card of a finished proposal; an answer or a skip (V11) resumes a run parked on its
/// question. Any note goes through the backend's screen before anything stores it.
sealed class MealPlanSessionMessage {
  const MealPlanSessionMessage();

  Map<String, dynamic> toJson();
}

/// Find another meal for the card whose meal is [slot], optionally with a [note]. [week] is every card's meal as
/// the screen shows it now, in card order, after any local swap or Undo: the server locks and scores against it.
final class SwapMessage extends MealPlanSessionMessage {
  const SwapMessage({required this.slot, required this.week, this.note});

  /// The corpus id of the meal on the card being swapped.
  final String slot;
  final List<String> week;
  final String? note;

  @override
  Map<String, dynamic> toJson() => <String, dynamic>{
    'type': 'swap',
    'slot': slot,
    'note': note,
    'week': week,
  };
}

/// The household's answer to the agent's one question: an [option] it offered, a [note], or both.
final class AnswerMessage extends MealPlanSessionMessage {
  const AnswerMessage({this.option, this.note});

  final String? option;
  final String? note;

  @override
  Map<String, dynamic> toJson() => <String, dynamic>{
    'type': 'answer',
    'option': option,
    'note': note,
  };
}

/// "Skip, just plan": resume the parked run without an answer.
final class SkipMessage extends MealPlanSessionMessage {
  const SkipMessage();

  @override
  Map<String, dynamic> toJson() => <String, dynamic>{'type': 'skip'};
}

/// The `202` body from posting a message. [swapId] is set for a swap: the id its outcome carries on the poll.
/// [noteDropped] is true when the message carried a note the screen dropped ("Couldn't use that note").
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanMessageAccepted {
  const MealPlanMessageAccepted({
    required this.sessionId,
    this.swapId,
    this.noteDropped = false,
  });

  factory MealPlanMessageAccepted.fromJson(Map<String, dynamic> json) =>
      _$MealPlanMessageAcceptedFromJson(json);

  final String sessionId;
  final int? swapId;
  final bool noteDropped;
}

/// The newest swap on a session, as a poll reports it. [replacement] is the meal now in slot [position] once
/// [state] is done; [note] says whether the swap note was used.
@JsonSerializable(fieldRename: FieldRename.snake, createToJson: false)
class MealPlanSessionSwap {
  const MealPlanSessionSwap({
    required this.swapId,
    required this.slot,
    required this.position,
    required this.state,
    this.note = MealPlanSwapNote.none,
    this.replacement,
  });

  factory MealPlanSessionSwap.fromJson(Map<String, dynamic> json) =>
      _$MealPlanSessionSwapFromJson(json);

  final int swapId;
  final String slot;
  final int position;
  @JsonKey(unknownEnumValue: MealPlanSwapState.unknown)
  final MealPlanSwapState state;
  @JsonKey(unknownEnumValue: MealPlanSwapNote.unknown)
  final MealPlanSwapNote note;
  final MealPlanRecipe? replacement;
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
    this.swap,
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

  /// The newest swap, once the household has asked for one (V10). Null from a backend without swaps.
  final MealPlanSessionSwap? swap;

  /// Echoed by the backend for logs; the app already knows the id it is polling.
  final String? sessionId;

  /// When the session last changed. Observability only: V1 renders whatever status comes back and has no
  /// staleness logic.
  final DateTime? updatedAt;

  /// `done`, `failed` and `cancelled` end a Generate attempt; everything else keeps polling.
  bool get isTerminal =>
      status == MealPlanSessionStatus.done ||
      status == MealPlanSessionStatus.failed ||
      status == MealPlanSessionStatus.cancelled;
}
