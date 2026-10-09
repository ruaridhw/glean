/// Pure presentation logic for the Plan screen, ported from the Expo app's
/// `src/plan/presentation.ts` (see git history). No Riverpod/widget
/// dependency here —
/// everything is a plain function over data the screen already has, so it's
/// unit-testable without a widget harness.
library;

import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/util/week.dart';

/// One row in the Dinners list: either a real entry, or an empty slot the
/// user can tap to add a dinner.
///
/// RN numbered every slot ("1", "2", ...) even though slots aren't
/// day-mapped — "1" meant "first added", not Monday — which the spec calls
/// out as misleading (FLUTTER_MIGRATION.md §6). This port drops the number
/// entirely rather than perpetuate it; [key] exists only for Flutter's
/// widget identity, never rendered.
class PlanSlot {
  const PlanSlot({required this.key, required this.entry});

  final String key;

  /// Null for an empty, fillable slot.
  final MealPlanEntryView? entry;
}

/// Builds the full slot list for a week: one [PlanSlot] per existing entry,
/// plus enough empty slots to reach [target] (never negative — a week that
/// has rolled past its target, e.g. because cooked meals freed up slots
/// that then got refilled, shows zero empty slots rather than a negative
/// count).
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

/// The human-readable range for the week starting [weekStart] (a Monday —
/// see `lib/data/util/week.dart`), e.g. `21–27 Jul` or, spanning a month
/// boundary, `28 Jul – 3 Aug`.
///
/// RN's equivalent (`getCurrentWeekRangeLabel`) only ever computed this for
/// "now" — there was no pagination to format any other week. This takes an
/// explicit [weekStart] instead of implicitly using the current date, since
/// AC-PLAN-02 requires paging to arbitrary weeks, each needing its own label.
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

/// The "N dinners left to plan" hint under the progress ring.
///
/// Takes [remaining] — the already-computed per-week capacity
/// (`PlanRepository.remainingCapacityForWeek` / `planWeekRemainingCapacityProvider`,
/// AC-PLAN-04) — directly, rather than re-deriving `target - plannedCount`
/// itself the way RN's `getPlanHint(planned, target)` did. That RN formula
/// is exactly wrong once cooked meals stop counting (AC-PLAN-03): a week
/// with 2 cooked + 1 uncooked entries against a target of 2 has already
/// freed a slot (remaining = 1), which `target - entries.length` (2 - 3 =
/// -1) cannot express.
String planHint(int remaining) {
  if (remaining <= 0) return 'Week fully planned — nice';
  return '$remaining dinner${remaining == 1 ? '' : 's'} left to plan this week';
}

/// A day-boundary check matching the RN "expired or within 2 days" tone
/// used for both the pantry's expiry badge and this nudge (ported from the
/// Expo app's `src/pantry/presentation.ts`'s `getExpiryBadge`/
/// `isExpiringSoon`, see git history).
///
/// Duplicated here rather than imported: the Pantry feature (which would
/// own the Flutter equivalent) is a parallel, not-yet-landed wave, and this
/// is a small enough pure check that porting it twice is cheaper than a
/// cross-feature import — see the final report for this as a flagged seam.
bool _isExpiringSoon(PantryItemView item, DateTime now) {
  final DateTime? expiry = item.expiryDate;
  if (expiry == null) return false;
  final DateTime today = DateTime(now.year, now.month, now.day);
  final int days = expiry.difference(today).inDays;
  return days <= 2;
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
      .where((PantryItemView item) => _isExpiringSoon(item, effectiveNow))
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
