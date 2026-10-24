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

  @override
  InterviewState build() => const InterviewState();

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

  /// Drops the whole interview, which is what Skip all means: nothing is saved and the transcript is gone.
  void reset() {
    _pending = null;
    state = const InterviewState();
  }

  /// Stores the profile the household just confirmed. Returns false when the save failed, so the page can say
  /// so and let first run carry on — a profile that did not save must not block stocking the pantry.
  Future<bool> confirm() async {
    final InterviewDone? done = state.done;
    if (done == null) return false;
    try {
      await ref
          .read(householdProfileRepositoryProvider)
          .save(userId: ref.read(currentUserIdProvider), profile: done.profile);
      return true;
    } catch (_) {
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
              draftProfile: const HouseholdProfile(),
            ),
          );
    } on ApiException catch (error) {
      if (!ref.mounted) return;
      state = before.copyWith(pending: false, failure: error);
      return;
    }
    if (!ref.mounted) return;

    _pending = null;
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
