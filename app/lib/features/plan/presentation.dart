/// Pure presentation logic for the Plan screen: plain functions over data the screen already has,
/// unit-testable without a widget harness.
library;

import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/pantry/pantry_presentation.dart'
    show isExpiringSoon;

/// One row in the Dinners list: either a real entry, or an empty slot the user can tap to add a dinner. Slots
/// aren't day-mapped, so they carry no number; [key] exists only for widget identity and is never rendered.
class PlanSlot {
  const PlanSlot({required this.key, required this.entry});

  final String key;

  /// Null for an empty, fillable slot.
  final MealPlanEntryView? entry;
}

/// Builds the full slot list for a week: one [PlanSlot] per existing entry plus enough empty slots to reach
/// [target], never negative (a week that has rolled past its target shows zero empty slots).
List<PlanSlot> buildPlanSlots(List<MealPlanEntryView> entries, int target) {
  final List<PlanSlot> slots = <PlanSlot>[
    for (final MealPlanEntryView entry in entries)
      PlanSlot(key: 'entry-${entry.id}', entry: entry),
  ];
  final uncooked = entries.where((entry) => !entry.isCooked).length;
  final int emptyCount = target > uncooked ? target - uncooked : 0;
  for (int i = 0; i < emptyCount; i++) {
    slots.add(PlanSlot(key: 'empty-$i', entry: null));
  }
  return slots;
}

const List<String> _months = <String>[
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/// The human-readable range for the week starting [weekStart] (a Monday, see `lib/data/util/week.dart`), e.g.
/// `21–27 Jul` or, across a month boundary, `28 Jul – 3 Aug`.
String weekRangeLabel(DateTime weekStart) {
  final DateTime start = dateOnly(weekStart);
  final DateTime end = start.add(const Duration(days: 6));
  if (start.month == end.month) {
    return '${start.day}–${end.day} ${_months[start.month - 1]}';
  }
  return '${start.day} ${_months[start.month - 1]} – ${end.day} ${_months[end.month - 1]}';
}

/// Whether [weekStart] is the week containing "now" — drives the pager's
/// "This week" label and lets the screen distinguish "today's plan" from a
/// paged-to week at a glance.
bool isCurrentWeek(DateTime weekStart) {
  return dateOnly(weekStart) == startOfWeek(DateTime.now());
}

/// The "N dinners left to plan" hint under the progress ring. Takes the already-computed per-week [remaining]
/// capacity rather than deriving `target - plannedCount`, which is wrong once cooked meals stop counting: 2
/// cooked + 1 uncooked against a target of 2 has already freed a slot.
String planHint(int remaining) {
  if (remaining <= 0) return 'Week fully planned — nice';
  return '$remaining dinner${remaining == 1 ? '' : 's'} left to plan this week';
}

/// Nudge shown on the Plan screen about pantry items expiring soon, so a
/// user plans a dinner that uses them up before they're wasted. Returns
/// null when nothing is urgent, so the caller can hide the banner entirely.
class PlanExpiryNudge {
  const PlanExpiryNudge({
    required this.count,
    required this.title,
    required this.message,
  });

  final int count;
  final String title;
  final String message;
}

PlanExpiryNudge? planExpiryNudge(List<PantryItemView> items, {DateTime? now}) {
  final DateTime effectiveNow = now ?? DateTime.now();
  final List<PantryItemView> urgent = items
      .where((PantryItemView item) => isExpiringSoon(item, now: effectiveNow))
      .toList();
  if (urgent.isEmpty) return null;

  final List<String> names = urgent
      .map((PantryItemView item) => item.canonicalName)
      .toList();
  final String preview = names.length <= 2
      ? names.join(' and ')
      : '${names.take(2).join(', ')} and ${names.length - 2} more';
  final bool single = urgent.length == 1;
  return PlanExpiryNudge(
    count: urgent.length,
    title: single
        ? '1 item needs using up'
        : '${urgent.length} items need using up',
    message:
        '$preview ${single ? 'is' : 'are'} expiring soon — plan a dinner to '
        'use ${single ? 'it' : 'them'} up.',
  );
}
