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
