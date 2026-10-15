// Week-boundary helpers. Weeks run Monday-Sunday (ISO 8601, Monday = 1): the spec states no boundary, so it
// is fixed once here. Every repository method taking a `weekStart` expects a Monday from `startOfWeek`, and the
// Plan feature must use these helpers rather than derive its own boundary.
//
// Dates are plain `YYYY-MM-DD` text; only the date, never the time, matters.

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
