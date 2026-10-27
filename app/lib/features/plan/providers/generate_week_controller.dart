/// Corpus generation is one reviewed proposal (ADR 0019): create a backend session, poll it to a terminal
/// status while the proposal screen shows its progress, then save the whole week in one transaction when the
/// user taps Add to plan. Nothing reaches the plan before that tap, and a swap is local until it too is saved.
///
/// "Find another" (V10) asks the same session for a replacement for one card: the card shows the swap's own
/// progress lines while the rest of the review stays usable, and the replacement lands in that card's slot with
/// an Undo swap that is local. One swap runs at a time.
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/meal_plan_session.dart';
import 'package:glean/api/models/planning_profile.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/recipe_proposal.dart';
import 'package:glean/data/repositories/plan_repository.dart'
    show GeneratedWeekCommit, PlanEntryState, SwappedEntrySnapshot;
import 'package:glean/data/util/week.dart';

import '../compression.dart';
import '../food_groups.dart';
import '../generate_failure.dart';
import '../week_feedback.dart';

/// How the session loop waits and measures. Injected so a test can drive the whole 1 s cadence and the 5 min cap
/// without real delays: production sleeps for real and reads the wall clock.
class GenerateSessionPoller {
  const GenerateSessionPoller({
    required this.sleep,
    required this.now,
    this.interval = const Duration(seconds: 1),
    this.cap = const Duration(minutes: 5),
  });

  final Future<void> Function(Duration) sleep;
  final DateTime Function() now;

  /// The polling cadence the session design settles on. Progress lines arrive on the poll that wrote them.
  final Duration interval;

  /// The cap on a run. A session that never reports a terminal status (the network died between create and the
  /// last poll) ends the attempt as `stalled` rather than spinning forever. Nothing polls while the agent's question
  /// is on screen, and the cap starts again from the answer: the household's thinking time is never counted.
  final Duration cap;
}

final generateSessionPollerProvider = Provider<GenerateSessionPoller>(
  (ref) => GenerateSessionPoller(
    sleep: (Duration duration) => Future<void>.delayed(duration),
    now: ref.watch(clockProvider),
  ),
);

/// Which face the proposal screen is showing. [question] is the focused question step: the agent asked its one
/// question, the session is parked as `waiting_for_user`, and nothing polls until the household answers or skips.
enum GenerateProposalPhase { idle, working, question, proposal, failed }

/// What the household did with the agent's question, so the working face can say "You answered: Two." once the
/// step gives way to the progress again. [noteDropped] is set when the backend could not use the note.
class GenerateQuestionReply {
  const GenerateQuestionReply({
    this.option,
    this.skipped = false,
    this.noteDropped = false,
  });

  final String? option;
  final bool skipped;
  final bool noteDropped;

  GenerateQuestionReply _withNoteDropped() => GenerateQuestionReply(
    option: option,
    skipped: skipped,
    noteDropped: true,
  );
}

/// What one Add to plan request did. The screen acts only on [GenerateSaveSaved]: a request refused because a
/// save is already in flight, or one whose review was discarded, must not close the review or show a snackbar.
sealed class GenerateSaveOutcome {
  const GenerateSaveOutcome();
}

/// A real save. [commit] is what Undo restores; [inserted] is how many new meals were added.
final class GenerateSaveSaved extends GenerateSaveOutcome {
  const GenerateSaveSaved({required this.inserted, required this.commit});

  final int inserted;
  final GeneratedWeekCommit commit;
}

/// The controller already had a save in flight, so this request changed nothing.
final class GenerateSaveIgnored extends GenerateSaveOutcome {
  const GenerateSaveIgnored();
}

/// The review was discarded while the save was still resolving, before its transaction started.
final class GenerateSaveCancelled extends GenerateSaveOutcome {
  const GenerateSaveCancelled();
}

/// The save failed; the review's failed face shows the catalogue copy.
final class GenerateSaveFailed extends GenerateSaveOutcome {
  const GenerateSaveFailed(this.failure);

  final GenerateFailure failure;
}

/// The one "Find another" in flight: which card, the note it was sent with, and the swap's progress lines.
class FindAnotherState {
  const FindAnotherState({
    required this.index,
    this.note,
    this.progress = const <String>[],
  });

  /// Index into `result.suggestions` of the card being swapped.
  final int index;
  final String? note;
  final List<String> progress;

  FindAnotherState withProgress(List<String> lines) => FindAnotherState(
    index: index,
    note: note,
    progress: <String>[...progress, ...lines],
  );
}

/// What a card showed right before "Find another" replaced its meal, which Undo swap puts back exactly: the
/// server's meal for that slot and, if the household had taken it, the card's alternative.
class ReplacedMeal {
  const ReplacedMeal({required this.suggestion, this.alternativeShown});

  final MealPlanRecipe suggestion;
  final MealPlanRecipe? alternativeShown;
}

/// One plain line on a card after a swap. [problem] is true when the swap itself did not work (it reads as an
/// error); a swap that worked but dropped its note says so in a neutral voice.
class CardNotice {
  const CardNotice(this.text, {this.problem = true});

  final String text;
  final bool problem;
}

/// The card copy for a swap's outcomes. Plain words, never a status code.
const String swapFailedCopy = "Couldn't find another right now. Try again.";
const String swapNothingElseCopy = 'Nothing else fits this slot right now.';
const String swapNoteDroppedCopy = "Couldn't use that note";
const String swapStillFinishingCopy =
    'Your last swap is still finishing. Try again in a moment.';

/// Everything one Generate attempt holds: its arguments, its progress, its proposal, and the local swaps the
/// user has made but not saved. A swap is a suggestion, not a write; [swaps] and [plannedSwaps] stay in memory
/// until Add to plan commits them.
class GenerateProposalState {
  const GenerateProposalState({
    this.phase = GenerateProposalPhase.idle,
    this.weekStart,
    this.slots = 0,
    this.servings = 0,
    this.sessionId,
    this.progress = const <String>[],
    this.result,
    this.failure,
    this.question,
    this.sendingReply = false,
    this.questionError,
    this.reply,
    this.swaps = const <int, MealPlanRecipe>{},
    this.plannedSwaps = const <int, MealPlanRecipe>{},
    this.saving = false,
    this.committing = false,
    this.cursor = 0,
    this.findingAnother,
    this.replacedFrom = const <int, ReplacedMeal>{},
    this.cardNotices = const <int, CardNotice>{},
  });

  final GenerateProposalPhase phase;

  /// The week the proposal would fill; null when nothing has started.
  final DateTime? weekStart;
  final int slots;
  final int servings;
  final String? sessionId;

  /// Human lines the worker wrote, oldest first, as they arrived.
  final List<String> progress;
  final MealPlanResponse? result;

  /// Set when the attempt ended in a failure. With [result] present it is a failed save, and Retry saves again
  /// rather than planning a new week.
  final GenerateFailure? failure;

  /// The agent's question while [phase] is [GenerateProposalPhase.question].
  final MealPlanSessionQuestion? question;

  /// True while the answer (or the skip) is on its way. The step stays up, its buttons disabled, until the server
  /// has it, so a send that fails loses neither the question nor what was chosen.
  final bool sendingReply;

  /// Why the last send failed, shown on the step beside Send and Skip so either can be tried again.
  final String? questionError;

  /// What the household answered, once it has.
  final GenerateQuestionReply? reply;

  /// Index into `result.suggestions` -> the alternative the user chose. An absent index is the original pick.
  final Map<int, MealPlanRecipe> swaps;

  /// Plan entry id -> the alternative the user chose for a meal already in the week.
  final Map<int, MealPlanRecipe> plannedSwaps;

  /// True while Add to plan resolves recipes and commits; the button is disabled so a double-tap can't run the
  /// transaction twice.
  final bool saving;

  /// True once Add to plan has passed its abort point and the transaction is running. Back may abort a save
  /// while it is resolving details, but not once the transaction has started: by then the review must not be
  /// discarded underneath a commit.
  final bool committing;

  /// The session's poll cursor after the last poll, so a swap's polls show only that swap's lines.
  final int cursor;

  /// The "Find another" in flight, if any. Only one runs at a time.
  final FindAnotherState? findingAnother;

  /// Index -> what the card showed before a "Find another" replaced it, which Undo swap puts back. Local, like
  /// every swap.
  final Map<int, ReplacedMeal> replacedFrom;

  /// Index -> one plain line on that card: a swap's error, "nothing else fits", or "Couldn't use that note".
  final Map<int, CardNotice> cardNotices;

  bool isReplaced(int index) => replacedFrom.containsKey(index);

  /// The meal a card shows: the chosen alternative when there is one, else the server's suggestion.
  MealPlanRecipe suggestionAt(int index) =>
      swaps[index] ?? result!.suggestions[index];

  bool isSwapped(int index) => swaps.containsKey(index);

  /// True while an attempt is under way: planning, or parked on the agent's question. A second Generate must not
  /// start over either.
  bool get inFlight =>
      phase == GenerateProposalPhase.working ||
      phase == GenerateProposalPhase.question;

  /// True when there is a proposal to show but nothing the user asked to change, so Add to plan has no work: a
  /// done session with an empty suggestion list is the no-meals edge state.
  bool get hasProposal =>
      phase == GenerateProposalPhase.proposal &&
      result != null &&
      result!.suggestions.isNotEmpty;

  GenerateProposalState _copy({
    GenerateProposalPhase? phase,
    String? sessionId,
    List<String>? progress,
    MealPlanResponse? result,
    GenerateFailure? failure,
    MealPlanSessionQuestion? question,
    bool clearQuestion = false,
    bool? sendingReply,
    String? questionError,
    bool clearQuestionError = false,
    GenerateQuestionReply? reply,
    Map<int, MealPlanRecipe>? swaps,
    Map<int, MealPlanRecipe>? plannedSwaps,
    bool? saving,
    bool? committing,
    int? cursor,
    FindAnotherState? findingAnother,
    bool clearFindingAnother = false,
    Map<int, ReplacedMeal>? replacedFrom,
    Map<int, CardNotice>? cardNotices,
  }) => GenerateProposalState(
    phase: phase ?? this.phase,
    weekStart: weekStart,
    slots: slots,
    servings: servings,
    sessionId: sessionId ?? this.sessionId,
    progress: progress ?? this.progress,
    result: result ?? this.result,
    failure: failure ?? this.failure,
    question: clearQuestion ? null : question ?? this.question,
    sendingReply: sendingReply ?? this.sendingReply,
    questionError: clearQuestionError
        ? null
        : questionError ?? this.questionError,
    reply: reply ?? this.reply,
    swaps: swaps ?? this.swaps,
    plannedSwaps: plannedSwaps ?? this.plannedSwaps,
    saving: saving ?? this.saving,
    committing: committing ?? this.committing,
    cursor: cursor ?? this.cursor,
    findingAnother: clearFindingAnother
        ? null
        : findingAnother ?? this.findingAnother,
    replacedFrom: replacedFrom ?? this.replacedFrom,
    cardNotices: cardNotices ?? this.cardNotices,
  );
}

class GenerateWeekController extends Notifier<GenerateProposalState> {
  /// Bumped whenever an attempt is superseded (cancel, a new run). A poll or save that finishes after that
  /// must not touch the state it no longer owns.
  int _attempt = 0;

  /// Bumped by every "Find another" and by cancelling one, so a swap's poll that returns after it was cancelled
  /// or replaced changes nothing.
  int _finds = 0;

  /// True from a Cancel until the server next accepts a swap: the cancelled swap may still be running there, so a
  /// refusal means "wait for it", not "something went wrong".
  bool _cancelledSwapMayRun = false;

  /// Where the next poll of the current session starts, kept while the question is on screen so the poll that
  /// follows the answer does not repeat progress lines.
  int _cursor = 0;

  /// The week's note this attempt sent with its request, so the poll that ends it (which may follow the answer to
  /// the agent's question) can tell the week box whether the note was used.
  String? _sentWeekNote;

  @override
  GenerateProposalState build() => const GenerateProposalState();

  bool _owns(int attempt) =>
      attempt == _attempt && state.phase == GenerateProposalPhase.working;

  /// Opens the review immediately in its working state, then plans in the background. The screen watches
  /// [state], so the first frame is already the working face rather than a spinner on the Plan tab.
  Future<void> generate({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    if (state.inFlight) return;
    if (slots <= 0) return;
    // A session a failed attempt left behind may still be running (a lost poll, a stalled cap): cancel it before
    // paying for a new one, so it cannot finish unseen beside the next. A proposal's session is already done.
    final String? leftOver = state.phase == GenerateProposalPhase.failed
        ? state.sessionId
        : null;
    final int attempt = ++_attempt;
    _cursor = 0;
    state = GenerateProposalState(
      phase: GenerateProposalPhase.working,
      weekStart: weekStart,
      slots: slots,
      servings: servings,
    );
    if (leftOver != null) await _cancelSession(leftOver);
    if (attempt != _attempt) return;
    await _run(attempt, weekStart: weekStart, slots: slots, servings: servings);
  }

  /// Repeats whatever failed: a lost session is planned again; a failed save retries the save from the
  /// proposal already on screen, since resolving and committing are the only work left there. Returns how many
  /// outcome, so the screen reports a retried save exactly as Add to plan would. A retried run has no save
  /// outcome to act on.
  Future<GenerateSaveOutcome> retry() async {
    final GenerateProposalState failed = state;
    if (failed.failure == null) return const GenerateSaveIgnored();
    if (failed.result != null) return addToPlan();
    final DateTime? weekStart = failed.weekStart;
    if (weekStart == null) return const GenerateSaveIgnored();
    await generate(
      weekStart: weekStart,
      slots: failed.slots,
      servings: failed.servings,
    );
    return const GenerateSaveIgnored();
  }

  /// Cancel and Back: stop watching the session, discard everything, and ask the server to cancel it. A
  /// terminal session is left as it was by the server, so calling this after the result is harmless.
  Future<void> cancel() async {
    final String? session = state.sessionId;
    _attempt++;
    state = const GenerateProposalState();
    if (session != null) await _cancelSession(session);
  }

  /// The working state is the whole app here, so a failed DELETE must not trap the user on the screen; the
  /// session expires on its own TTL at worst.
  Future<void> _cancelSession(String sessionId) async {
    try {
      await ref.read(apiClientProvider).cancelMealPlanSession(sessionId);
    } on ApiException catch (_) {
      // Best effort: the discard is already local.
    }
  }

  /// Sends the household's answer to the agent's question (an option, a note, or both) and returns to the
  /// progress. The poll that follows has a fresh cap: the time spent on the question is never counted.
  Future<void> answerQuestion({String? option, String? note}) {
    final String? trimmed = note?.trim();
    final String? sentNote = trimmed == null || trimmed.isEmpty
        ? null
        : trimmed;
    if (option == null && sentNote == null) return Future<void>.value();
    return _sendReply(
      AnswerMessage(option: option, note: sentNote),
      GenerateQuestionReply(option: option),
    );
  }

  /// "Skip, just plan": the run resumes without an answer.
  Future<void> skipQuestion() => _sendReply(
    const SkipMessage(),
    const GenerateQuestionReply(skipped: true),
  );

  Future<void> _sendReply(
    MealPlanSessionMessage message,
    GenerateQuestionReply reply,
  ) async {
    final String? sessionId = state.sessionId;
    if (state.phase != GenerateProposalPhase.question ||
        state.sendingReply ||
        sessionId == null) {
      return;
    }
    final int attempt = _attempt;
    state = state._copy(sendingReply: true, clearQuestionError: true);
    var noteDropped = false;
    try {
      final MealPlanMessageAccepted accepted = await ref
          .read(apiClientProvider)
          .sendMealPlanSessionMessage(sessionId, message);
      noteDropped = accepted.noteDropped;
    } on ApiException catch (error) {
      // 409: the session is no longer waiting, because this answer already landed (a send that timed out after the
      // server took it, then retried) or it moved on. Polling shows which.
      if (error is! ApiServerException || error.statusCode != 409) {
        if (_asking(attempt)) {
          // Keep the question and what was chosen: Send or Skip can be tried again, and nothing new is paid for.
          state = state._copy(
            sendingReply: false,
            questionError: error is ApiRateLimitException
                ? GenerateFailure.fromApi(error).message
                : "Couldn't send that. Try again.",
          );
        }
        return;
      }
    }
    if (!_asking(attempt)) return;
    // The server has it: the step gives way to the progress, which says what was answered.
    state = state._copy(
      phase: GenerateProposalPhase.working,
      clearQuestion: true,
      sendingReply: false,
      reply: noteDropped ? reply._withNoteDropped() : reply,
    );
    await _poll(attempt, sessionId);
  }

  /// Whether [attempt] still owns the question step: Back cancels it while a send is in flight.
  bool _asking(int attempt) =>
      attempt == _attempt && state.phase == GenerateProposalPhase.question;

  /// Locally takes the suggestion's alternative, or puts the original back. No network and no write.
  void swapSuggestion(int index) {
    final MealPlanResponse? result = state.result;
    if (result == null || index < 0 || index >= result.suggestions.length) {
      return;
    }
    final Map<int, MealPlanRecipe> next = Map<int, MealPlanRecipe>.of(
      state.swaps,
    );
    if (next.remove(index) == null) {
      final MealPlanRecipe? alternative = result.suggestions[index].alternative;
      if (alternative != null) next[index] = alternative;
    }
    state = state._copy(swaps: next);
  }

  /// Locally swaps a meal already in the week for its planned alternative, or back to the planned meal.
  void swapPlanned(int entryId, MealPlanRecipe alternative) {
    final Map<int, MealPlanRecipe> next = Map<int, MealPlanRecipe>.of(
      state.plannedSwaps,
    );
    if (next.remove(entryId) == null) next[entryId] = alternative;
    state = state._copy(plannedSwaps: next);
  }

  /// "Find another" for card [index]: sends a swap, with [note] if one was typed, and follows it on the session's
  /// polls until the replacement lands in the same slot. Ignored while another swap runs, while saving, or with
  /// no proposal. Every outcome but a replacement leaves the card as it was, with a plain line saying why.
  Future<void> findAnother(int index, {String? note}) async {
    final GenerateProposalState before = state;
    final MealPlanResponse? result = before.result;
    final String? sessionId = before.sessionId;
    if (before.phase != GenerateProposalPhase.proposal ||
        result == null ||
        sessionId == null ||
        before.findingAnother != null ||
        before.saving ||
        index < 0 ||
        index >= result.suggestions.length) {
      return;
    }
    // The week as the household sees it: a local alternative or Undo on any card counts, so the server locks
    // and scores what is on screen, not its own copy of the proposal.
    final List<String?> shown = <String?>[
      for (int i = 0; i < result.suggestions.length; i++)
        before.suggestionAt(i).externalId,
    ];
    final String? slot = shown[index];
    if (slot == null || shown.contains(null)) return;
    final List<String> week = shown.cast<String>();
    final String trimmed = note?.trim() ?? '';
    final String? sent = trimmed.isEmpty ? null : trimmed;
    final int attempt = _attempt;
    final int find = ++_finds;
    state = before._copy(
      findingAnother: FindAnotherState(index: index, note: sent),
      cardNotices: Map<int, CardNotice>.of(before.cardNotices)..remove(index),
    );

    final api = ref.read(apiClientProvider);
    if (_cancelledSwapMayRun) {
      // The cancelled swap may have written lines since the last poll. Start this swap's cursor past them, so the
      // card shows only its own: if the old swap is still running, the server refuses this one anyway.
      try {
        final MealPlanSessionUpdate latest = await api.getMealPlanSession(
          sessionId,
          after: state.cursor,
        );
        if (!_findsAnother(attempt, find)) return;
        state = state._copy(cursor: latest.nextCursor);
      } on ApiException catch (_) {
        // A missed read only risks showing an old line; the swap itself can still go ahead.
      }
    }
    final MealPlanMessageAccepted accepted;
    try {
      accepted = await api.sendMealPlanSessionMessage(
        sessionId,
        SwapMessage(slot: slot, week: week, note: sent),
      );
    } on ApiException catch (error) {
      _endFind(attempt, find, index, notice: _swapRefusedCopy(error));
      return;
    }
    _cancelledSwapMayRun = false;

    final GenerateSessionPoller poller = ref.read(
      generateSessionPollerProvider,
    );
    final DateTime startedAt = poller.now();
    var cursor = state.cursor;
    while (_findsAnother(attempt, find)) {
      if (poller.now().difference(startedAt) >= poller.cap) {
        _endFind(attempt, find, index, notice: swapFailedCopy);
        return;
      }
      try {
        final MealPlanSessionUpdate update = await api.getMealPlanSession(
          sessionId,
          after: cursor,
        );
        if (!_findsAnother(attempt, find)) return;
        cursor = update.nextCursor;
        state = state._copy(
          cursor: cursor,
          findingAnother: state.findingAnother!.withProgress(update.progress),
        );
        final MealPlanSessionSwap? swap = update.swap;
        if (swap != null &&
            swap.swapId == accepted.swapId &&
            swap.state != MealPlanSwapState.pending) {
          _land(attempt, find, index, swap, noteDropped: accepted.noteDropped);
          return;
        }
        if (update.status == MealPlanSessionStatus.failed) {
          _endFind(attempt, find, index, notice: swapFailedCopy);
          return;
        }
        if (update.status == MealPlanSessionStatus.cancelled) {
          // The session was cancelled under the swap: it will never finish, so the card recovers.
          _endFind(attempt, find, index, notice: swapFailedCopy);
          return;
        }
      } on ApiException catch (error) {
        // As for the run: a 404 cannot recover, anything else is one missed poll and the cap ends it.
        if (error is ApiServerException && error.statusCode == 404) {
          _endFind(attempt, find, index, notice: swapFailedCopy);
          return;
        }
      }
      await poller.sleep(poller.interval);
    }
  }

  /// Puts card [index] back exactly as it was before "Find another" replaced its meal: the alternative, if the
  /// household had taken it, else the meal. Local and instant, like every swap.
  void undoReplacement(int index) {
    final MealPlanResponse? result = state.result;
    final ReplacedMeal? previous = state.replacedFrom[index];
    if (result == null ||
        previous == null ||
        index >= result.suggestions.length) {
      return;
    }
    final MealPlanRecipe? alternative = previous.alternativeShown;
    state = state._copy(
      result: _withSuggestion(result, index, previous.suggestion),
      replacedFrom: Map<int, ReplacedMeal>.of(state.replacedFrom)
        ..remove(index),
      swaps: Map<int, MealPlanRecipe>.of(state.swaps)
        ..remove(index)
        ..addAll(<int, MealPlanRecipe>{index: ?alternative}),
      cardNotices: Map<int, CardNotice>.of(state.cardNotices)..remove(index),
    );
  }

  /// Stops watching the swap in flight and puts its card back as it was. The server may still finish that swap;
  /// its result is ignored, and the next swap sends the week on screen, so nothing it wrote can reach this review.
  void cancelFindAnother() {
    if (state.findingAnother == null) return;
    _finds++;
    _cancelledSwapMayRun = true;
    state = state._copy(clearFindingAnother: true);
  }

  /// The card's line when the server would not take a swap.
  String _swapRefusedCopy(ApiException error) {
    if (error is ApiRateLimitException) {
      return GenerateFailure.fromApi(error).message;
    }
    if (error is ApiServerException &&
        error.statusCode == 409 &&
        _cancelledSwapMayRun) {
      return swapStillFinishingCopy;
    }
    return swapFailedCopy;
  }

  bool _findsAnother(int attempt, int find) =>
      attempt == _attempt &&
      find == _finds &&
      state.phase == GenerateProposalPhase.proposal &&
      state.findingAnother != null;

  void _endFind(
    int attempt,
    int find,
    int index, {
    String? notice,
    bool problem = true,
  }) {
    if (!_findsAnother(attempt, find)) return;
    state = state._copy(
      clearFindingAnother: true,
      cardNotices: <int, CardNotice>{
        ...state.cardNotices,
        if (notice != null) index: CardNotice(notice, problem: problem),
      },
    );
  }

  /// The swap finished: a replacement takes the card's slot (and its own Undo), anything else is a line on the
  /// card. The rest of the review, and any local swap on another card, stays as the household left it.
  void _land(
    int attempt,
    int find,
    int index,
    MealPlanSessionSwap swap, {
    bool noteDropped = false,
  }) {
    final MealPlanResponse? result = state.result;
    final MealPlanRecipe? replacement = swap.replacement;
    if (swap.state == MealPlanSwapState.noReplacement) {
      _endFind(attempt, find, index, notice: swapNothingElseCopy);
      return;
    }
    if (swap.state != MealPlanSwapState.done ||
        replacement == null ||
        result == null) {
      _endFind(attempt, find, index, notice: swapFailedCopy);
      return;
    }
    state = state._copy(
      result: _withSuggestion(result, index, replacement),
      replacedFrom: <int, ReplacedMeal>{
        ...state.replacedFrom,
        index: ReplacedMeal(
          suggestion: result.suggestions[index],
          alternativeShown: state.swaps[index],
        ),
      },
      swaps: Map<int, MealPlanRecipe>.of(state.swaps)..remove(index),
    );
    _endFind(
      attempt,
      find,
      index,
      notice: noteDropped || swap.note == MealPlanSwapNote.dropped
          ? swapNoteDroppedCopy
          : null,
      // The swap worked; only its note was left out.
      problem: false,
    );
  }

  MealPlanResponse _withSuggestion(
    MealPlanResponse result,
    int index,
    MealPlanRecipe meal,
  ) => MealPlanResponse(
    suggestions: <MealPlanRecipe>[
      for (int i = 0; i < result.suggestions.length; i++)
        i == index ? meal : result.suggestions[i],
    ],
    weekSummary: result.weekSummary,
    plannedAlternatives: result.plannedAlternatives,
    degraded: result.degraded,
  );

  /// Saves the whole review in one transaction: the new meals (with any local swaps applied) into the empty
  /// slots, and a swapped planned meal by updating its own entry. Nothing is written before this call.
  ///
  /// Returns how many new meals were inserted. Recipe details are fetched before the transaction opens, so no
  /// network call runs inside it.
  Future<GenerateSaveOutcome> addToPlan() async {
    final GenerateProposalState attempt = state;
    final MealPlanResponse? result = attempt.result;
    final DateTime? weekStart = attempt.weekStart;
    // A swap in flight would change the week after it was saved: Add waits for it (or for its Cancel).
    if (result == null ||
        weekStart == null ||
        attempt.saving ||
        attempt.findingAnother != null) {
      return const GenerateSaveIgnored();
    }
    // A save that Back discards while it is still resolving must never reach the transaction.
    final int saveAttempt = _attempt;
    state = attempt._copy(saving: true);
    try {
      final String userId = ref.read(currentUserIdProvider);
      final entries = await ref
          .read(planRepositoryProvider)
          .getWeek(userId: userId, weekStart: weekStart);

      final List<MealPlanRecipe> chosen = <MealPlanRecipe>[
        for (int i = 0; i < result.suggestions.length; i++)
          attempt.suggestionAt(i),
      ];
      final List<RecipeView> resolved = await _resolveSuggestions(
        chosen,
        userId: userId,
        entries: entries,
      );

      // Resolve planned swaps before the transaction, for the same reason.
      final List<({int entryId, RecipeView recipe, int servings})>
      plannedUpdates = <({int entryId, RecipeView recipe, int servings})>[];
      for (final MapEntry<int, MealPlanRecipe> swap
          in attempt.plannedSwaps.entries) {
        final MealPlanEntryView? entry = entries
            .where((MealPlanEntryView value) => value.id == swap.key)
            .firstOrNull;
        if (entry == null) continue;
        final RecipeView recipe = await _resolveOne(swap.value, userId: userId);
        plannedUpdates.add((
          entryId: entry.id,
          recipe: recipe,
          servings: entry.servings,
        ));
      }

      if (resolved.isEmpty && plannedUpdates.isEmpty) {
        // The review had meals, so saving none of them is a failure to show, not a quiet no-op.
        throw const GenerateFailure(GenerateFailureKind.unknown);
      }
      // Back aborts a save that is still resolving, so re-check the attempt before the transaction starts.
      if (saveAttempt != _attempt) return const GenerateSaveCancelled();
      state = state._copy(committing: true);

      final ({int inserted, GeneratedWeekCommit commit})
      saved = await ref.read(gleanDatabaseProvider).transaction(() async {
        final plan = ref.read(planRepositoryProvider);
        final shopping = ref.read(shoppingRepositoryProvider);
        // Re-check inside the transaction: manual additions while the review was open must not overfill
        // the week or duplicate a now-planned recipe.
        final List<MealPlanEntryView> current = await plan.getWeek(
          userId: userId,
          weekStart: weekStart,
        );
        final int remaining = await plan.remainingCapacityForWeek(
          userId: userId,
          weekStart: weekStart,
        );
        final Set<int?> currentIds = current
            .map((MealPlanEntryView entry) => entry.recipeId)
            .toSet();
        final List<PlanEntryState> addedEntries = <PlanEntryState>[];
        for (final RecipeView recipe in resolved) {
          if (addedEntries.length >= remaining) break;
          if (currentIds.contains(recipe.id)) continue;
          final int entryId = await plan.addEntry(
            userId: userId,
            recipeId: recipe.id,
            recipeTitle: recipe.title,
            servings: attempt.servings,
            plannedDate: weekStart,
          );
          await shopping.addGapsForRecipe(
            userId: userId,
            recipeId: recipe.id,
            servings: attempt.servings,
            sourceMealPlanEntryId: entryId,
          );
          addedEntries.add(
            await plan.snapshotEntryState(entryId: entryId, userId: userId),
          );
        }
        final List<SwappedEntrySnapshot> swappedEntries =
            <SwappedEntrySnapshot>[];
        for (final ({int entryId, RecipeView recipe, int servings}) update
            in plannedUpdates) {
          final PlanEntryState before = await plan.snapshotEntryState(
            entryId: update.entryId,
            userId: userId,
          );
          await plan.replaceEntryRecipe(
            entryId: update.entryId,
            userId: userId,
            recipeId: update.recipe.id,
            recipeTitle: update.recipe.title,
          );
          await shopping.clearGapsForEntry(
            userId: userId,
            mealPlanEntryId: update.entryId,
          );
          await shopping.addGapsForRecipe(
            userId: userId,
            recipeId: update.recipe.id,
            servings: update.servings,
            sourceMealPlanEntryId: update.entryId,
          );
          swappedEntries.add(
            SwappedEntrySnapshot(
              before: before,
              after: await plan.snapshotEntryState(
                entryId: update.entryId,
                userId: userId,
              ),
            ),
          );
        }
        return (
          inserted: addedEntries.length,
          commit: GeneratedWeekCommit(
            addedEntries: addedEntries,
            swappedEntries: swappedEntries,
          ),
        );
      });
      // The review was discarded while the transaction ran? The screen blocks that, but never report a save
      // to a state that no longer owns it.
      if (saveAttempt != _attempt) return const GenerateSaveCancelled();
      _attempt++;
      state = const GenerateProposalState();
      return GenerateSaveSaved(inserted: saved.inserted, commit: saved.commit);
    } catch (error) {
      final GenerateFailure failure = GenerateFailure.from(error);
      if (saveAttempt == _attempt) {
        state = attempt._copy(
          phase: GenerateProposalPhase.failed,
          saving: false,
          failure: failure,
        );
      }
      return GenerateSaveFailed(failure);
    }
  }

  /// Puts the week back as it was before the last Add to plan. The screen captures the commit at save time and
  /// passes it to the Undo snackbar, so a later Add cannot change what an older Undo restores.
  Future<void> undoAddToPlan(GeneratedWeekCommit commit) => ref
      .read(planRepositoryProvider)
      .undoGeneratedWeek(
        userId: ref.read(currentUserIdProvider),
        commit: commit,
      );

  Future<void> _run(
    int attempt, {
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    try {
      final MealPlanRequest request = await _buildRequest(
        weekStart: weekStart,
        slots: slots,
        servings: servings,
      );
      if (!_owns(attempt)) return;
      _sentWeekNote = request.humanFeedback?.note;

      final api = ref.read(apiClientProvider);
      final MealPlanSessionCreated session;
      try {
        session = await api.createMealPlanSession(request);
      } on ApiException catch (error) {
        _fail(attempt, GenerateFailure.fromApi(error));
        return;
      }
      if (!_owns(attempt)) {
        // Cancelled between create and the first poll: the session exists, so ask the server to drop it.
        await _cancelSession(session.sessionId);
        return;
      }
      state = state._copy(sessionId: session.sessionId);
      await _poll(attempt, session.sessionId);
    } catch (error) {
      _fail(attempt, GenerateFailure.from(error));
    }
  }

  /// Polls [sessionId] every second until it ends, asks its question, or the cap passes. The cap is measured from
  /// this call, so a poll loop restarted after the household's answer never counts the time it spent answering.
  Future<void> _poll(int attempt, String sessionId) async {
    try {
      final api = ref.read(apiClientProvider);
      final GenerateSessionPoller poller = ref.read(
        generateSessionPollerProvider,
      );
      final DateTime startedAt = poller.now();
      while (true) {
        if (poller.now().difference(startedAt) >= poller.cap) {
          _fail(attempt, const GenerateFailure(GenerateFailureKind.stalled));
          return;
        }
        try {
          final MealPlanSessionUpdate update = await api.getMealPlanSession(
            sessionId,
            after: _cursor,
          );
          if (!_owns(attempt)) return;
          _cursor = update.nextCursor;
          switch (update.status) {
            case MealPlanSessionStatus.done:
              final MealPlanResponse? result = update.result;
              // A done session that carries no plan is a broken response, not an empty week.
              if (result == null) {
                _fail(
                  attempt,
                  const GenerateFailure(GenerateFailureKind.unknown),
                );
                return;
              }
              state = state._copy(
                phase: GenerateProposalPhase.proposal,
                progress: <String>[...state.progress, ...update.progress],
                result: result,
                cursor: _cursor,
              );
              // The box says "Couldn't use that note" when the screen dropped it; the chips applied anyway.
              final DateTime? weekStart = state.weekStart;
              if (weekStart != null) {
                ref
                    .read(weekFeedbackProvider(weekStart).notifier)
                    .noteOutcome(
                      sentNote: _sentWeekNote,
                      outcome: result.feedbackNote,
                    );
              }
              return;
            case MealPlanSessionStatus.failed:
              _fail(
                attempt,
                GenerateFailure.fromCode(
                  update.error?.code,
                  retryAfterMinutes: update.error?.retryAfterMinutes,
                ),
              );
              return;
            case MealPlanSessionStatus.cancelled:
              // Only this app cancels its own session; a poll that still sees it stop is a discard, not a
              // failure to show. The screen was already left.
              if (attempt == _attempt) state = const GenerateProposalState();
              return;
            case MealPlanSessionStatus.waitingForUser
                when update.question != null:
              // The agent asked its one question: show it and stop polling. The answer (or the skip) resumes the
              // run, and polling with it, from this cursor.
              state = state._copy(
                phase: GenerateProposalPhase.question,
                question: update.question,
                progress: <String>[...state.progress, ...update.progress],
              );
              return;
            default:
              // queued, running, a waiting session with no question to show, or a status this build does not
              // know: keep the working state and poll again.
              if (update.progress.isNotEmpty) {
                state = state._copy(
                  progress: <String>[...state.progress, ...update.progress],
                );
              }
              break;
          }
        } on ApiException catch (error) {
          // A 404 means the server holds no such session (expired, or never this user's); polling cannot
          // recover it. Anything else is one missed poll, not a failed run: keep polling, and let the cap end
          // the run if they never stop.
          if (error is ApiServerException && error.statusCode == 404) {
            _fail(attempt, const GenerateFailure(GenerateFailureKind.unknown));
            return;
          }
        }
        await poller.sleep(poller.interval);
        if (!_owns(attempt)) return;
      }
    } catch (error) {
      _fail(attempt, GenerateFailure.from(error));
    }
  }

  void _fail(int attempt, GenerateFailure failure) {
    if (!_owns(attempt)) return;
    state = state._copy(
      phase: GenerateProposalPhase.failed,
      failure: failure,
      saving: false,
    );
  }

  /// Resolves the server's picks to recipes saved on this phone, fetching and saving details for corpus recipes
  /// the library does not hold yet. Excludes anything already planned and de-duplicates, exactly as the sync
  /// path did; a detail fetch that fails is skipped so one bad pick does not lose the rest.
  Future<List<RecipeView>> _resolveSuggestions(
    List<MealPlanRecipe> picks, {
    required String userId,
    required List<MealPlanEntryView> entries,
  }) async {
    final recipes = ref.read(recipesRepositoryProvider);
    final saved = await recipes.getSaved(userId);
    final plannedIds = entries
        .map((MealPlanEntryView entry) => entry.recipeId)
        .toSet();
    final excluded = <String>{
      for (final MealPlanEntryView entry in entries)
        if (entry.externalIdSnapshot != null) entry.externalIdSnapshot!,
      for (final RecipeView recipe in saved)
        if (plannedIds.contains(recipe.id) && recipe.externalId != null)
          recipe.externalId!,
    };
    final resolved = <RecipeView>[];
    final seenIds = <int>{};
    for (final MealPlanRecipe pick in picks) {
      RecipeView? recipe;
      if (pick.externalId != null) {
        if (!excluded.add(pick.externalId!)) continue;
        recipe = await _resolveCorpus(pick.externalId!, userId: userId);
        if (recipe == null) continue;
      } else {
        // Defensive saved-mode compatibility: never accept another user's id.
        recipe = saved
            .where((RecipeView value) => value.id == pick.recipeId)
            .firstOrNull;
        if (recipe == null) {
          throw StateError('Meal plan suggested an unknown recipe');
        }
      }
      if (seenIds.add(recipe.id)) resolved.add(recipe);
    }
    return resolved;
  }

  /// Resolves one explicitly chosen meal (a planned meal's swap), where a fetch failure is a failure of the
  /// save rather than a pick to skip.
  Future<RecipeView> _resolveOne(
    MealPlanRecipe pick, {
    required String userId,
  }) async {
    if (pick.externalId != null) {
      final RecipeView? recipe = await _resolveCorpus(
        pick.externalId!,
        userId: userId,
      );
      if (recipe == null) {
        throw StateError('The alternative could not be fetched');
      }
      return recipe;
    }
    final recipes = ref.read(recipesRepositoryProvider);
    final saved = await recipes.getSaved(userId);
    final RecipeView? recipe = saved
        .where((RecipeView value) => value.id == pick.recipeId)
        .firstOrNull;
    if (recipe == null) {
      throw StateError('Meal plan suggested an unknown recipe');
    }
    return recipe;
  }

  /// The saved recipe for a corpus id, fetching and storing its detail when the library does not have it yet.
  /// Returns null when the detail fetch fails.
  Future<RecipeView?> _resolveCorpus(
    String externalId, {
    required String userId,
  }) async {
    final recipes = ref.read(recipesRepositoryProvider);
    final RecipeView? saved = await recipes.getByExternalId(
      externalId: externalId,
      userId: userId,
    );
    if (saved != null) return saved;
    final RecipeOut detail;
    try {
      detail = await ref.read(recipeDetailProvider(externalId).future);
    } catch (_) {
      return null;
    }
    final int id = await saveRecipeProposal(recipes, userId, detail);
    return recipes.getById(id: id, userId: userId);
  }

  Future<MealPlanRequest> _buildRequest({
    required DateTime weekStart,
    required int slots,
    required int servings,
  }) async {
    final userId = ref.read(currentUserIdProvider);
    final recipes = ref.read(recipesRepositoryProvider);
    final plan = ref.read(planRepositoryProvider);
    final pantry = await ref.read(pantryRepositoryProvider).getAll(userId);
    final saved = await recipes.getSaved(userId);
    final entries = await plan.getWeek(userId: userId, weekStart: weekStart);
    // The window plus any older cook that still carries a thumbs down: a dislike does not expire.
    final cooked = await plan.plannerHistory(userId: userId);
    final config = await ref.read(userConfigRepositoryProvider).get(userId);
    // The profile shapes the plan: dislikes are never planned and the scorer leans to the rest.
    final profile = await ref
        .read(householdProfileRepositoryProvider)
        .get(userId);
    final groups = <int, List<String>>{};
    for (final recipe in saved) {
      groups[recipe.id] = await foodGroupsForRecipe(recipes, recipe.id);
    }
    final plannedIds = entries.map((entry) => entry.recipeId).toSet();
    final excluded = <String>{
      for (final entry in entries)
        if (entry.externalIdSnapshot != null) entry.externalIdSnapshot!,
      for (final recipe in saved)
        if (plannedIds.contains(recipe.id) && recipe.externalId != null)
          recipe.externalId!,
    };
    // One clock for the pantry slice and the date it was measured from: across local midnight they
    // must not disagree about which day `expires_in_days` counts from.
    final now = DateTime.now();
    final HumanFeedbackRequest? feedback = ref
        .read(weekFeedbackProvider(weekStart))
        .toRequest();
    return MealPlanRequest(
      humanFeedback: feedback,
      profile: planningProfileJson(profile),
      source: 'corpus',
      excludeExternalIds: excluded.toList(),
      pantry: compressPantry(pantry, now: now),
      recipeHistory: [
        for (final recipe in saved)
          RecipeHistoryItem(
            recipeId: recipe.id,
            title: recipe.title,
            lastCookedAt: recipe.lastCookedAt,
            foodGroups: groups[recipe.id] ?? [],
          ),
      ],
      cookedHistory: [
        for (final entry in cooked)
          CookedHistoryItem(
            recipeId: entry.externalIdSnapshot,
            title: entry.recipeTitle,
            // UTC, with the offset the wire format needs: a local wall clock read as UTC aged a
            // 41d23h-old cook past the six-week floor in a UTC-7 zone.
            cookedAt: entry.cookedAt!.toUtc(),
            // The latest thumb and its note, if any; the backend keeps a thumbs-down recipe out of the
            // week and reads nothing else from either.
            rating: entry.rating?.dbValue,
            note: entry.note,
          ),
      ],
      foodGroupCoverage: foodGroupCoverageForWeek(entries, groups),
      purchaseTolerance: config.purchaseTolerance,
      mealsPerWeek: slots,
      dietaryFlags: config.dietaryFlags,
      maxActiveTimeMins: config.maxActiveTimeMins,
      localDate: formatDate(now),
    );
  }
}

final generateWeekControllerProvider =
    NotifierProvider<GenerateWeekController, GenerateProposalState>(
      GenerateWeekController.new,
    );
