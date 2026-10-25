/// What the household tells the planner about one week: chips and an optional note (the "This week" box).
///
/// Held in memory, one selection per week, keyed by the week's start: nothing is set by default, a new week
/// starts empty, and closing the app clears it too. Nothing here is written to the database, so the box needs
/// no schema change. What each chip does to the plan is the backend's (`meal_plan.tools.FeedbackChip`); this
/// file only names them for the screen and the wire.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/meal_plan.dart';

/// The note's limit, in Unicode code points: the backend's `MAX_FEEDBACK_NOTE_LENGTH`.
const int maxWeekNoteLength = 200;

enum FeedbackChip {
  quickWeeknights('quick_weeknights', 'Quick weeknights'),
  useUpTheFridge('use_up_the_fridge', 'Use up the fridge'),
  somethingNew('something_new', 'Something new'),
  healthier('healthier', 'Healthier'),
  comfortFood('comfort_food', 'Comfort food'),
  lighter('lighter', 'Lighter'),
  guests('guests', 'Guests'),
  sameAsLastWeek('same_as_last_week', 'Same as last week');

  const FeedbackChip(this.wire, this.label);

  /// The value the backend's `HumanFeedback.chips` takes.
  final String wire;
  final String label;
}

/// The backend's `feedback_note` values that mean the note was dropped.
const Set<String> _droppedNoteOutcomes = <String>{
  'not_a_preference',
  'unavailable',
};

class WeekFeedback {
  const WeekFeedback({
    this.chips = const <FeedbackChip>{},
    this.note = '',
    this.noteUnused = false,
  });

  final Set<FeedbackChip> chips;
  final String note;

  /// True when the last plan could not use [note]. The chips applied anyway; editing the note clears this.
  final bool noteUnused;

  bool get hasNote => note.trim().isNotEmpty;
  bool get isEmpty => chips.isEmpty && !hasNote;

  /// The chips in the order the box shows them, whatever order they were tapped in.
  List<FeedbackChip> get orderedChips => <FeedbackChip>[
    for (final FeedbackChip chip in FeedbackChip.values)
      if (chips.contains(chip)) chip,
  ];

  /// The collapsed box's one line: "Nothing set", or the chips and whether there is a note.
  String get summary {
    if (isEmpty) return 'Nothing set';
    return <String>[
      for (final FeedbackChip chip in orderedChips) chip.label,
      if (hasNote) noteUnused ? "note couldn't be used" : 'note',
    ].join(' · ');
  }

  /// What Generate sends, or null when nothing is set (the backend's default).
  HumanFeedbackRequest? toRequest() => isEmpty
      ? null
      : HumanFeedbackRequest(
          chips: <String>[
            for (final FeedbackChip chip in orderedChips) chip.wire,
          ],
          note: hasNote ? note.trim() : null,
        );

  WeekFeedback _copy({
    Set<FeedbackChip>? chips,
    String? note,
    bool? noteUnused,
  }) => WeekFeedback(
    chips: chips ?? this.chips,
    note: note ?? this.note,
    noteUnused: noteUnused ?? this.noteUnused,
  );
}

/// One week's selection. Keyed by the week's start (`startOfWeek`), so when the week rolls over the Plan tab
/// reads a new, empty selection and last week's is never sent again.
final weekFeedbackProvider =
    NotifierProvider.family<WeekFeedbackController, WeekFeedback, DateTime>(
      WeekFeedbackController.new,
    );

class WeekFeedbackController extends Notifier<WeekFeedback> {
  WeekFeedbackController(this.weekStart);

  final DateTime weekStart;

  @override
  WeekFeedback build() => const WeekFeedback();

  void toggle(FeedbackChip chip) {
    final Set<FeedbackChip> next = Set<FeedbackChip>.of(state.chips);
    if (!next.remove(chip)) next.add(chip);
    state = state._copy(chips: next);
  }

  void setNote(String note) {
    if (note == state.note) return;
    state = state._copy(note: note, noteUnused: false);
  }

  void clear() => state = const WeekFeedback();

  /// Records what the plan did with the note it was sent. A note edited since then is a different note, so
  /// the outcome is ignored for it.
  void noteOutcome({required String? sentNote, required String? outcome}) {
    if (sentNote == null || sentNote != state.note.trim()) return;
    state = state._copy(noteUnused: _droppedNoteOutcomes.contains(outcome));
  }
}
