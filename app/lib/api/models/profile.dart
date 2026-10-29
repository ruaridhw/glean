/// The wire shapes of `POST /profile/interview`: stateless and one paid call per turn, so the app sends the
/// whole transcript so far with each answer and the backend replies with either the next question or the
/// finished profile and its two-line summary for the household to confirm.
///
/// Hand-written rather than generated because the response is a tagged union (`status`), and because the
/// profile inside it is the app's own versioned [HouseholdProfile] rather than a second generated copy.
library;

import '../../data/models/household_profile.dart';

/// A profile field a question can target, as this build knows the contract's names.
enum ProfileField {
  favouriteMeals('favourite_meals'),
  lovedIngredients('loved_ingredients'),
  dislikedIngredients('disliked_ingredients'),
  cuisinesLiked('cuisines_liked'),
  cuisinesAvoided('cuisines_avoided'),
  proteinTargets('protein_targets'),
  spiceTolerance('spice_tolerance'),
  habits('habits'),
  household('household'),
  notes('notes');

  const ProfileField(this.wireValue);

  final String wireValue;

  static ProfileField? parse(Object? value) {
    for (final ProfileField field in values) {
      if (field.wireValue == value) return field;
    }
    return null;
  }
}

/// One question the interview asks. Every question is skippable; [options] is empty for a free-text one.
class InterviewQuestion {
  const InterviewQuestion({
    required this.id,
    required this.text,
    required this.field,
    this.options = const <String>[],
    this.skippable = true,
  });

  factory InterviewQuestion.fromJson(Map<String, dynamic> json) =>
      InterviewQuestion(
        id: _required(json, 'id'),
        text: _required(json, 'text'),
        field: switch (json['field']) {
          final String value => value,
          _ => null,
        },
        options: <String>[
          if (json['options'] case final List<dynamic> options)
            for (final Object? option in options)
              if (option is String) option,
        ],
        skippable: json['skippable'] != false,
      );

  final String id;
  final String text;

  /// The targeted field, kept exactly as the backend named it rather than as a value this build happens to
  /// know: the transcript replays every question verbatim, and the backend requires a field it recognises, so
  /// sending `null` for a newer build's field would fail the whole rest of the interview with a 422.
  final String? field;

  /// [field] as this build understands it, or `null` for one it does not know yet.
  ProfileField? get knownField => ProfileField.parse(field);

  final List<String> options;
  final bool skippable;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'id': id,
    'text': text,
    'options': options,
    'field': field,
    'skippable': skippable,
  };
}

/// What the household said to one question: some free text, some of the offered [options], or neither when
/// they skipped it. Skipping is an answer — it tells the interviewer to move on.
class InterviewAnswer {
  /// What the backend accepts for [text]; anything longer is a rejected request, so the composer stops there.
  static const int maxTextLength = 2000;

  const InterviewAnswer({
    this.text,
    this.options = const <String>[],
    this.skipped = false,
    this.clear = false,
  });

  factory InterviewAnswer.fromJson(Map<String, dynamic> json) =>
      InterviewAnswer(
        text: json['text'] is String ? json['text'] as String : null,
        options: <String>[
          if (json['options'] case final List<dynamic> options)
            for (final Object? option in options)
              if (option is String) option,
        ],
        skipped: json['skipped'] == true,
        clear: json['clear'] == true,
      );

  final String? text;
  final List<String> options;
  final bool skipped;
  final bool clear;

  Map<String, dynamic> toJson() {
    if (clear && (text != null || options.isNotEmpty || skipped)) {
      throw ArgumentError('Clear cannot accompany text, options or skipped');
    }
    return <String, dynamic>{
      'text': text,
      'options': options,
      'skipped': skipped,
      if (clear) 'clear': true,
    };
  }
}

/// One exchange: the question asked and the answer given, as the transcript replays it.
class InterviewTurn {
  const InterviewTurn({required this.question, required this.answer});

  factory InterviewTurn.fromJson(Map<String, dynamic> json) => InterviewTurn(
    question: InterviewQuestion.fromJson(
      json['question']! as Map<String, dynamic>,
    ),
    answer: InterviewAnswer.fromJson(json['answer']! as Map<String, dynamic>),
  );

  final InterviewQuestion question;
  final InterviewAnswer answer;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'question': question.toJson(),
    'answer': answer.toJson(),
  };
}

/// The body of `POST /profile/interview`. [draftProfile] is the profile the app knows about so far: empty for
/// a first interview, since only the server can turn answers into profile fields.
class InterviewRequest {
  const InterviewRequest({
    required this.transcript,
    required this.draftProfile,
    this.retake = false,
  });

  final List<InterviewTurn> transcript;
  final HouseholdProfile draftProfile;
  final bool retake;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'transcript': <Map<String, dynamic>>[
      for (final InterviewTurn turn in transcript) turn.toJson(),
    ],
    'draft_profile': draftProfile.toJson(),
    if (retake) 'retake': true,
  };
}

/// Either the next question or the finished profile. [droppedAnswer] says the last free-text answer failed
/// the backend's injection screen, so the household is told it could not be used.
sealed class InterviewResponse {
  const InterviewResponse({required this.droppedAnswer});

  /// Decodes a response body. Throws [FormatException] on a shape this build does not understand, which
  /// `GleanApiClient` turns into an `ApiParseException`.
  factory InterviewResponse.fromJson(Map<String, dynamic> json) =>
      switch (json['status']) {
        'question' => InterviewQuestionResponse(
          question: InterviewQuestion.fromJson(
            json['question']! as Map<String, dynamic>,
          ),
          turn: _int(json, 'turn'),
          maxTurns: _int(json, 'max_turns'),
          droppedAnswer: json['dropped_answer'] == true,
        ),
        'done' => InterviewDone(
          profile: HouseholdProfile.fromJson(
            json['profile']! as Map<String, dynamic>,
          ),
          summary: _required(json, 'summary'),
          updatedFields: _updatedFields(json['updated_fields']),
          droppedAnswer: json['dropped_answer'] == true,
        ),
        final Object? status => throw FormatException(
          'unknown interview status: $status',
        ),
      };

  final bool droppedAnswer;
}

/// The next question, and where the interview is up to: [turn] is 1-based.
final class InterviewQuestionResponse extends InterviewResponse {
  const InterviewQuestionResponse({
    required this.question,
    required this.turn,
    required this.maxTurns,
    required super.droppedAnswer,
  });

  final InterviewQuestion question;
  final int turn;
  final int maxTurns;
}

/// The finished profile and the two short lines the household confirms before it is saved.
final class InterviewDone extends InterviewResponse {
  const InterviewDone({
    required this.profile,
    required this.summary,
    this.updatedFields = const <String>{},
    required super.droppedAnswer,
  });

  final HouseholdProfile profile;
  final String summary;
  final Set<String> updatedFields;
}

Set<String> _updatedFields(Object? value) {
  if (value == null) return const <String>{};
  if (value is! List<dynamic>) {
    throw const FormatException('Invalid interview targets');
  }
  return <String>{
    for (final Object? field in value)
      if (field is String &&
          ProfileField.parse(field) != null &&
          field != 'notes')
        field
      else
        throw const FormatException('Invalid interview target'),
  };
}

String _required(Map<String, dynamic> json, String key) => switch (json[key]) {
  final String value => value,
  _ => throw FormatException('interview response is missing "$key"'),
};

int _int(Map<String, dynamic> json, String key) => switch (json[key]) {
  final int value => value,
  _ => throw FormatException('interview response is missing "$key"'),
};
