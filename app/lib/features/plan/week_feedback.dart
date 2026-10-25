/// What the household tells the planner about one week: chips and an optional note (the "This week" box).
///
/// One selection per week, keyed by the week's start: nothing is set by default and a new week starts empty.
/// It survives a restart through [WeekFeedbackStore], a key-value entry in `flutter_secure_storage` (the store
/// the sign-in tokens already use), not the database, so the box needs no schema change. What each chip does to
/// the plan is the backend's (`meal_plan.tools.FeedbackChip`); this file only names them for the screen, the
/// wire and the store.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/auth/auth_controller.dart' show authControllerProvider;
import 'package:glean/data/models/meal_thumb.dart' show truncateRatingNote;
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/util/week.dart';

/// The note's limit, in Unicode code points: the backend's `MAX_FEEDBACK_NOTE_LENGTH`. Flutter's `maxLength`
/// counts grapheme clusters, which a skin-toned emoji makes smaller than the code-point count, so the note is
/// clipped with [clipWeekNote] instead.
const int maxWeekNoteLength = 200;

/// [note] cut to at most [maxWeekNoteLength] code points, never splitting a visible character.
String clipWeekNote(String note) =>
    truncateRatingNote(note, limit: maxWeekNoteLength);

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

  bool get _storable => !isEmpty || noteUnused;

  Map<String, dynamic> _toJson() => <String, dynamic>{
    'chips': <String>[for (final FeedbackChip chip in orderedChips) chip.wire],
    'note': note,
    'note_unused': noteUnused,
  };

  /// A stored entry, or null when it is not one this build can read. An unknown chip is skipped.
  static WeekFeedback? _fromJson(Object? json) {
    if (json is! Map) return null;
    final Object? chips = json['chips'];
    final Object? note = json['note'];
    return WeekFeedback(
      chips: <FeedbackChip>{
        if (chips is List)
          for (final FeedbackChip chip in FeedbackChip.values)
            if (chips.contains(chip.wire)) chip,
      },
      // An older build counted the note differently and may have saved a longer one.
      note: note is String ? clipWeekNote(note) : '',
      noteUnused: json['note_unused'] == true,
    );
  }

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

/// Where the selections are kept between launches: one JSON entry per user in `flutter_secure_storage`, a map
/// from week start (`2026-10-19`) to that week's chips and note. Weeks before the current one are never read
/// back and are dropped at the next write, so the box resets when the week rolls over.
class WeekFeedbackStore {
  WeekFeedbackStore({required this.clock, FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  /// Today, for deciding which weeks are over.
  final DateTime Function() clock;
  final FlutterSecureStorage _storage;

  static String keyFor(String userId) => 'glean_week_feedback.$userId';

  Future<WeekFeedback?> read(String userId, DateTime weekStart) async {
    final String week = _week(weekStart);
    if (week.compareTo(_currentWeek()) < 0) return null;
    return WeekFeedback._fromJson((await _weeks(userId))[week]);
  }

  Future<void> write(
    String userId,
    DateTime weekStart,
    WeekFeedback feedback,
  ) async {
    final Map<String, dynamic> weeks = await _weeks(userId);
    final String current = _currentWeek();
    // ISO dates order as strings: everything before this week is over.
    weeks.removeWhere((String week, _) => week.compareTo(current) < 0);
    final String week = _week(weekStart);
    if (feedback._storable) {
      weeks[week] = feedback._toJson();
    } else {
      weeks.remove(week);
    }
    if (weeks.isEmpty) {
      await _storage.delete(key: keyFor(userId));
    } else {
      await _storage.write(key: keyFor(userId), value: jsonEncode(weeks));
    }
  }

  String _currentWeek() => _week(clock());

  Future<Map<String, dynamic>> _weeks(String userId) async {
    final String? raw = await _storage.read(key: keyFor(userId));
    if (raw == null) return <String, dynamic>{};
    try {
      final Object? decoded = jsonDecode(raw);
      return decoded is Map<String, dynamic> ? decoded : <String, dynamic>{};
    } on FormatException {
      // A value this build cannot read is treated as nothing set; the next write replaces it.
      return <String, dynamic>{};
    }
  }

  static String _week(DateTime date) {
    final DateTime start = startOfWeek(date);
    String two(int value) => value.toString().padLeft(2, '0');
    return '${start.year}-${two(start.month)}-${two(start.day)}';
  }
}

final weekFeedbackStoreProvider = Provider<WeekFeedbackStore>(
  (Ref ref) => WeekFeedbackStore(clock: ref.watch(clockProvider)),
);

/// One week's selection. Keyed by the week's start (`startOfWeek`), so when the week rolls over the Plan tab
/// reads a new, empty selection and last week's is never sent again.
final weekFeedbackProvider =
    NotifierProvider.family<WeekFeedbackController, WeekFeedback, DateTime>(
      WeekFeedbackController.new,
    );

class WeekFeedbackController extends Notifier<WeekFeedback> {
  WeekFeedbackController(this.weekStart);

  final DateTime weekStart;

  bool _edited = false;
  Future<void> _writes = Future<void>.value();

  @override
  WeekFeedback build() {
    _edited = false;
    final String? userId = ref.watch(
      authControllerProvider.select((s) => s.userId),
    );
    if (userId != null) unawaited(_restore(userId));
    return const WeekFeedback();
  }

  /// Reads the saved selection back. A tap that lands before the read finishes wins: it is newer.
  Future<void> _restore(String userId) async {
    final WeekFeedback? saved = await ref
        .read(weekFeedbackStoreProvider)
        .read(userId, weekStart);
    if (saved == null || _edited || !ref.mounted) return;
    state = saved;
  }

  void _update(WeekFeedback next) {
    _edited = true;
    state = next;
    final String? userId = ref.read(authControllerProvider).userId;
    if (userId == null) return;
    final WeekFeedbackStore store = ref.read(weekFeedbackStoreProvider);
    // One write at a time, in order, so a fast run of taps can never leave an older selection saved last.
    _writes = _writes.then((_) => store.write(userId, weekStart, next)).catchError((
      Object _,
    ) {
      // Best effort: the selection still applies to this launch, it just is not kept for the next one.
    });
  }

  void toggle(FeedbackChip chip) {
    final Set<FeedbackChip> next = Set<FeedbackChip>.of(state.chips);
    if (!next.remove(chip)) next.add(chip);
    _update(state._copy(chips: next));
  }

  void setNote(String note) {
    final String clipped = clipWeekNote(note);
    if (clipped == state.note) return;
    _update(state._copy(note: clipped, noteUnused: false));
  }

  void clear() => _update(const WeekFeedback());

  /// Records what the plan did with the note it was sent. A note edited since then is a different note, so
  /// the outcome is ignored for it.
  void noteOutcome({required String? sentNote, required String? outcome}) {
    if (sentNote == null || sentNote != state.note.trim()) return;
    _update(state._copy(noteUnused: _droppedNoteOutcomes.contains(outcome)));
  }
}
