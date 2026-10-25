// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'meal_plan_session.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

MealPlanSessionCreated _$MealPlanSessionCreatedFromJson(
  Map<String, dynamic> json,
) => $checkedCreate('MealPlanSessionCreated', json, ($checkedConvert) {
  final val = MealPlanSessionCreated(
    sessionId: $checkedConvert('session_id', (v) => v as String),
  );
  return val;
}, fieldKeyMap: const {'sessionId': 'session_id'});

MealPlanSessionError _$MealPlanSessionErrorFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'MealPlanSessionError',
  json,
  ($checkedConvert) {
    final val = MealPlanSessionError(
      code: $checkedConvert('code', (v) => v as String),
      retryAfterMinutes: $checkedConvert(
        'retry_after_minutes',
        (v) => (v as num?)?.toInt(),
      ),
    );
    return val;
  },
  fieldKeyMap: const {'retryAfterMinutes': 'retry_after_minutes'},
);

MealPlanSessionQuestion _$MealPlanSessionQuestionFromJson(
  Map<String, dynamic> json,
) => $checkedCreate('MealPlanSessionQuestion', json, ($checkedConvert) {
  final val = MealPlanSessionQuestion(
    question: $checkedConvert('question', (v) => v as String),
    options: $checkedConvert(
      'options',
      (v) =>
          (v as List<dynamic>?)?.map((e) => e as String).toList() ??
          const <String>[],
    ),
    why: $checkedConvert('why', (v) => v as String? ?? ''),
  );
  return val;
});

MealPlanMessageAccepted _$MealPlanMessageAcceptedFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'MealPlanMessageAccepted',
  json,
  ($checkedConvert) {
    final val = MealPlanMessageAccepted(
      sessionId: $checkedConvert('session_id', (v) => v as String),
      swapId: $checkedConvert('swap_id', (v) => (v as num?)?.toInt()),
      noteDropped: $checkedConvert('note_dropped', (v) => v as bool? ?? false),
    );
    return val;
  },
  fieldKeyMap: const {
    'sessionId': 'session_id',
    'swapId': 'swap_id',
    'noteDropped': 'note_dropped',
  },
);

MealPlanSessionSwap _$MealPlanSessionSwapFromJson(Map<String, dynamic> json) =>
    $checkedCreate('MealPlanSessionSwap', json, ($checkedConvert) {
      final val = MealPlanSessionSwap(
        swapId: $checkedConvert('swap_id', (v) => (v as num).toInt()),
        slot: $checkedConvert('slot', (v) => v as String),
        position: $checkedConvert('position', (v) => (v as num).toInt()),
        state: $checkedConvert(
          'state',
          (v) => $enumDecode(
            _$MealPlanSwapStateEnumMap,
            v,
            unknownValue: MealPlanSwapState.unknown,
          ),
        ),
        note: $checkedConvert(
          'note',
          (v) =>
              $enumDecodeNullable(
                _$MealPlanSwapNoteEnumMap,
                v,
                unknownValue: MealPlanSwapNote.unknown,
              ) ??
              MealPlanSwapNote.none,
        ),
        replacement: $checkedConvert(
          'replacement',
          (v) => v == null
              ? null
              : MealPlanRecipe.fromJson(v as Map<String, dynamic>),
        ),
      );
      return val;
    }, fieldKeyMap: const {'swapId': 'swap_id'});

const _$MealPlanSwapStateEnumMap = {
  MealPlanSwapState.pending: 'pending',
  MealPlanSwapState.done: 'done',
  MealPlanSwapState.noReplacement: 'no_replacement',
  MealPlanSwapState.failed: 'failed',
  MealPlanSwapState.unknown: 'unknown',
};

const _$MealPlanSwapNoteEnumMap = {
  MealPlanSwapNote.none: 'none',
  MealPlanSwapNote.used: 'used',
  MealPlanSwapNote.dropped: 'dropped',
  MealPlanSwapNote.unknown: 'unknown',
};

MealPlanSessionUpdate _$MealPlanSessionUpdateFromJson(
  Map<String, dynamic> json,
) => $checkedCreate(
  'MealPlanSessionUpdate',
  json,
  ($checkedConvert) {
    final val = MealPlanSessionUpdate(
      status: $checkedConvert(
        'status',
        (v) => $enumDecode(
          _$MealPlanSessionStatusEnumMap,
          v,
          unknownValue: MealPlanSessionStatus.unknown,
        ),
      ),
      progress: $checkedConvert(
        'progress',
        (v) =>
            (v as List<dynamic>?)?.map((e) => e as String).toList() ??
            const <String>[],
      ),
      nextCursor: $checkedConvert(
        'next_cursor',
        (v) => (v as num?)?.toInt() ?? 0,
      ),
      result: $checkedConvert(
        'result',
        (v) => v == null
            ? null
            : MealPlanResponse.fromJson(v as Map<String, dynamic>),
      ),
      error: $checkedConvert(
        'error',
        (v) => v == null
            ? null
            : MealPlanSessionError.fromJson(v as Map<String, dynamic>),
      ),
      swap: $checkedConvert(
        'swap',
        (v) => v == null
            ? null
            : MealPlanSessionSwap.fromJson(v as Map<String, dynamic>),
      ),
      question: $checkedConvert(
        'question',
        (v) => v == null
            ? null
            : MealPlanSessionQuestion.fromJson(v as Map<String, dynamic>),
      ),
      sessionId: $checkedConvert('session_id', (v) => v as String?),
      updatedAt: $checkedConvert(
        'updated_at',
        (v) => v == null ? null : DateTime.parse(v as String),
      ),
    );
    return val;
  },
  fieldKeyMap: const {
    'nextCursor': 'next_cursor',
    'sessionId': 'session_id',
    'updatedAt': 'updated_at',
  },
);

const _$MealPlanSessionStatusEnumMap = {
  MealPlanSessionStatus.queued: 'queued',
  MealPlanSessionStatus.running: 'running',
  MealPlanSessionStatus.waitingForUser: 'waiting_for_user',
  MealPlanSessionStatus.done: 'done',
  MealPlanSessionStatus.failed: 'failed',
  MealPlanSessionStatus.cancelled: 'cancelled',
  MealPlanSessionStatus.unknown: 'unknown',
};
