/// The taste interview in progress: the transcript so far, the question on screen, and what the backend has
/// said. Each turn is one paid call to `POST /profile/interview`, so this holds the whole conversation the
/// screen shows and nothing restarts it while the household taps Back and forward through first run.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/profile.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';

/// Immutable, so every change the interview makes is one new value the page can watch.
class InterviewState {
  const InterviewState({
    this.transcript = const <InterviewTurn>[],
    this.droppedTurns = const <int>{},
    this.question,
    this.turn = 0,
    this.maxTurns = InterviewController.maxTurns,
    this.done,
    this.pending = false,
    this.failure,
  });

  /// Every exchange so far, in order. The question in [question] is not in here yet.
  final List<InterviewTurn> transcript;

  /// Indexes into [transcript] whose free-text answer the backend could not use.
  final Set<int> droppedTurns;

  /// The question waiting for an answer, or `null` while the first one is being fetched or after the last.
  final InterviewQuestion? question;

  /// The 1-based number of [question], as the backend counts turns.
  final int turn;
  final int maxTurns;

  /// The finished profile and its summary, once the backend has nothing more to ask.
  final InterviewDone? done;
  final bool pending;

  /// Why the last request failed, for the screen to turn into plain copy with a Retry.
  final Object? failure;

  bool get started =>
      question != null || done != null || pending || failure != null;

  bool get finished => done != null;

  InterviewState copyWith({
    List<InterviewTurn>? transcript,
    Set<int>? droppedTurns,
    InterviewQuestion? question,
    int? turn,
    int? maxTurns,
    InterviewDone? done,
    bool? pending,
    Object? failure,
    bool clearFailure = false,
  }) => InterviewState(
    transcript: transcript ?? this.transcript,
    droppedTurns: droppedTurns ?? this.droppedTurns,
    question: question ?? this.question,
    turn: turn ?? this.turn,
    maxTurns: maxTurns ?? this.maxTurns,
    done: done ?? this.done,
    pending: pending ?? this.pending,
    failure: clearFailure ? null : failure ?? this.failure,
  );
}

class InterviewController extends Notifier<InterviewState> {
  /// The cap the contract states. A response carries its own `max_turns`, which wins once it arrives.
  static const int maxTurns = 7;

  /// The exchange being sent, kept so Retry re-sends exactly what failed instead of losing the answer.
  InterviewTurn? _pending;

  /// Bumped by [reset]. A turn already on the wire belongs to the interview that was skipped, so its reply is
  /// dropped rather than allowed to put the conversation back on screen.
  int _generation = 0;

  HouseholdProfile? _baseline;
  final List<InterviewState> _history = <InterviewState>[];
  final Map<String, InterviewTurn> _drafted = <String, InterviewTurn>{};
  late String _userId;

  bool get canGoBack => _history.isNotEmpty;

  void back() {
    if (state.pending || _history.isEmpty) return;
    _pending = null;
    state = _history.removeLast();
  }

  void reviewAnswers() {
    if (_history.isEmpty) return;
    final first = _history.first;
    _history.clear();
    _pending = null;
    state = first;
  }

  @override
  InterviewState build() {
    _userId = ref.watch(currentUserIdProvider);
    _baseline = null;
    _history.clear();
    _drafted.clear();
    _pending = null;
    _generation++;
    ref.onDispose(() => _generation++);
    return const InterviewState();
  }

  Future<void> beginRetake(HouseholdProfile profile) async {
    reset();
    _baseline = profile;
    await begin();
  }

  /// Full staged intent, including explicit clears and selections, survives review navigation.
  InterviewAnswer? draftAnswer(InterviewQuestion question) {
    final prior = _drafted[question.id];
    return prior != null &&
            prior.question.text == question.text &&
            prior.question.field == question.field
        ? prior.answer
        : null;
  }

  /// Saved facts, not reconstructed historical answers or selected options.
  String prefill(InterviewQuestion question) {
    final HouseholdProfile? profile = _baseline;
    if (profile == null) return '';
    return switch (question.knownField) {
      ProfileField.favouriteMeals =>
        profile.favouriteMeals
            .map((FavouriteMeal meal) => meal.text)
            .join(', '),
      ProfileField.lovedIngredients => <String>[
        ...profile.lovedIngredients,
        ...profile.cuisinesLiked,
      ].join(', '),
      ProfileField.dislikedIngredients => <String>[
        ...profile.dislikedIngredients,
        ...profile.cuisinesAvoided,
      ].join(', '),
      ProfileField.cuisinesLiked => profile.cuisinesLiked.join(', '),
      ProfileField.cuisinesAvoided => profile.cuisinesAvoided.join(', '),
      ProfileField.habits => profile.habits,
      ProfileField.household => profile.household,
      ProfileField.spiceTolerance => profile.spiceTolerance?.name ?? '',
      ProfileField.proteinTargets =>
        profile.proteinTargets
            .map(
              (ProteinTarget target) =>
                  '${target.protein} ${target.minPerWeek == null ? '' : 'at least ${target.minPerWeek}'} ${target.maxPerWeek == null ? '' : 'at most ${target.maxPerWeek}'} times per week',
            )
            .join(', '),
      _ => '',
    };
  }

  Future<void> clearAnswer() async {
    final InterviewQuestion? asked = state.question;
    if (_baseline == null || asked == null || state.pending) return;
    _pending = InterviewTurn(
      question: asked,
      answer: const InterviewAnswer(clear: true),
    );
    await _send();
  }

  /// Asks the first question. Idempotent: coming back to the page picks the interview up where it was rather
  /// than paying for the openers again.
  Future<void> begin() async {
    if (state.started || state.pending) return;
    await _ask();
  }

  /// Sends free text and any chosen options as the answer to the question on screen. An answer with neither
  /// sends nothing: the household either chooses something or taps Skip.
  Future<void> answer({
    String? text,
    List<String> options = const <String>[],
  }) async {
    final InterviewQuestion? asked = state.question;
    if (asked == null || state.pending) return;
    final String? submitted = text?.trim();
    final bool hasText = submitted != null && submitted.isNotEmpty;
    if (!hasText && options.isEmpty) return;
    _pending = InterviewTurn(
      question: asked,
      answer: InterviewAnswer(
        text: hasText ? submitted : null,
        options: options,
      ),
    );
    await _send();
  }

  /// Skips the question on screen. The turn still goes to the backend, because skipping is an answer: it tells
  /// the interviewer to move on rather than to guess.
  Future<void> skip() async {
    final InterviewQuestion? asked = state.question;
    if (asked == null || state.pending) return;
    _pending = InterviewTurn(
      question: asked,
      answer: const InterviewAnswer(skipped: true),
    );
    await _send();
  }

  /// Re-sends what failed. The opener is not a turn in the transcript, so a failure before anything was sent
  /// has no exchange to replay: Retry asks for the first question again instead of doing nothing.
  Future<void> retry() => _send(sendNothing: _pending == null);

  /// Drops the whole interview, which is what Skip all means: nothing is saved and the transcript is gone. It
  /// stays available while a turn is in flight, because it is the way out of a slow one; [_generation] makes
  /// sure the reply that turn was waiting for cannot undo the skip.
  void reset() {
    _history.clear();
    _drafted.clear();
    _pending = null;
    _generation++;
    state = const InterviewState();
  }

  /// Stores the profile the household just confirmed. Returns false when the save failed, so the page can say
  /// so and let first run carry on — a profile that did not save must not block stocking the pantry.
  Future<bool> confirm() async {
    final InterviewDone? done = state.done;
    if (done == null) return false;
    try {
      if (ref.read(currentUserIdProvider) != _userId) return false;
      final HouseholdProfile? baseline = _baseline;
      if (baseline == null) {
        await ref
            .read(householdProfileRepositoryProvider)
            .save(userId: _userId, profile: done.profile);
      } else {
        await ref
            .read(householdProfileRepositoryProvider)
            .confirmInterview(
              userId: _userId,
              baseline: baseline,
              candidate: done.profile,
              fields: done.updatedFields,
            );
      }
      return true;
    } catch (error) {
      // First run reports local confirmation failures separately from paid request failures.
      if (ref.mounted && _baseline != null) {
        state = state.copyWith(failure: error);
      }
      return false;
    }
  }

  Future<void> _ask() async {
    // The openers come from an empty transcript: the backend owns the question order, not the app.
    _pending = null;
    await _send(sendNothing: true);
  }

  /// Posts the transcript, then either shows the next question or the summary. On failure the transcript stays
  /// exactly as it was and [_pending] keeps the answer for [retry].
  Future<void> _send({bool sendNothing = false}) async {
    final int generation = _generation;
    final InterviewState before = state;
    final InterviewTurn? next = _pending;
    if (!sendNothing && next == null) return;
    final List<InterviewTurn> transcript = <InterviewTurn>[
      ...before.transcript,
      ?next,
    ];
    state = before.copyWith(pending: true, clearFailure: true);

    final InterviewResponse response;
    try {
      response = await ref
          .read(apiClientProvider)
          .continueInterview(
            InterviewRequest(
              transcript: transcript,
              // A first interview starts from an empty profile: only the backend turns answers into fields.
              draftProfile: _baseline ?? const HouseholdProfile(),
              retake: _baseline != null,
            ),
          );
    } on ApiException catch (error) {
      if (!ref.mounted || generation != _generation) return;
      state = before.copyWith(pending: false, failure: error);
      return;
    }
    if (!ref.mounted || generation != _generation) return;

    _pending = null;
    if (next != null) {
      _history.add(before);
      _drafted[next.question.id] = next;
    }
    final Set<int> droppedTurns = <int>{
      ...before.droppedTurns,
      if (response.droppedAnswer) transcript.length - 1,
    };
    state = switch (response) {
      InterviewQuestionResponse(
        :final InterviewQuestion question,
        :final int turn,
        :final int maxTurns,
      ) =>
        InterviewState(
          transcript: transcript,
          droppedTurns: droppedTurns,
          question: question,
          turn: turn,
          maxTurns: maxTurns,
        ),
      InterviewDone done => InterviewState(
        transcript: transcript,
        droppedTurns: droppedTurns,
        turn: before.turn,
        maxTurns: before.maxTurns,
        done: done,
      ),
    };
  }
}

final NotifierProvider<InterviewController, InterviewState>
interviewControllerProvider =
    NotifierProvider<InterviewController, InterviewState>(
      InterviewController.new,
    );

final retakeInterviewControllerProvider =
    NotifierProvider.autoDispose<InterviewController, InterviewState>(
      InterviewController.new,
    );
