// Week-boundary helpers backing the Plan schema change (FLUTTER_MIGRATION.md
// §6 Plan): "This Week" gets an actual date filter, and rollover/capacity
// become week-scoped instead of lifetime (AC-PLAN-01/04/05).
//
// DELIBERATE CHOICE, not stated by the spec: weeks run Monday-Sunday (ISO
// 8601 weekday numbering: Monday = 1). The spec never states a week
// boundary, so this is the data layer's call, made once here rather than
// left for each caller to assume independently — every repository method
// that takes or returns a "week" (`PlanRepository.watchWeek`,
// `remainingCapacityForWeek`, `rolloverUncookedMeals`) treats `weekStart` as
// a Monday produced by `startOfWeek`, and the Plan feature (week pagination,
// "This Week" header, etc.) must go through these helpers rather than
// deriving its own week boundary, or the two will disagree.
//
// Dates are stored and compared as plain `YYYY-MM-DD` text — day-mapping
// within a week is explicitly out of scope (FLUTTER_MIGRATION.md §1), so
// only the date, never the time, matters here.

/// Midnight-local, date-only `DateTime` for `date` — strips any time-of-day
/// component so callers can't accidentally compare a `DateTime.now()` (which
/// carries a time) against these date-only values.
DateTime dateOnly(DateTime date) => DateTime(date.year, date.month, date.day);

/// The Monday that starts `date`'s week.
DateTime startOfWeek(DateTime date) {
  final day = dateOnly(date);
  return day.subtract(Duration(days: day.weekday - DateTime.monday));
}

/// The exclusive end of the week starting at `weekStart` (i.e. the following
/// Monday) — use as a `plannedDate < weekEnd` bound.
DateTime endOfWeek(DateTime weekStart) =>
    weekStart.add(const Duration(days: 7));

/// Formats a date-only `DateTime` as the `YYYY-MM-DD` text form used by
/// `planned_date`/`expiry_date` columns.
String formatDate(DateTime date) {
  final d = dateOnly(date);
  final y = d.year.toString().padLeft(4, '0');
  final m = d.month.toString().padLeft(2, '0');
  final day = d.day.toString().padLeft(2, '0');
  return '$y-$m-$day';
}

/// Parses a `YYYY-MM-DD` string back into a date-only `DateTime`.
DateTime parseDate(String value) => dateOnly(DateTime.parse(value));
