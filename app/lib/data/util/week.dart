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
  return addDays(date, DateTime.monday - date.weekday);
}

/// The exclusive end of the week starting at `weekStart` (i.e. the following
/// Monday) — use as a `plannedDate < weekEnd` bound.
DateTime endOfWeek(DateTime weekStart) => shiftWeeks(weekStart, 1);

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

/// Midnight-local `days` calendar days after (or, if negative, before) `date`. Never add a `Duration(days: n)` to a
/// calendar date: it is `n * 24` hours, which lands an hour off midnight across a clock change (and, with a
/// time-of-day, on the wrong date).
DateTime addDays(DateTime date, int days) =>
    DateTime(date.year, date.month, date.day + days);

/// The Monday `weeks` weeks after (or, if negative, before) `weekStart`.
DateTime shiftWeeks(DateTime weekStart, int weeks) =>
    addDays(weekStart, 7 * weeks);

/// Whole calendar days from `from` to `to`, ignoring time of day and clock changes (a spring-forward day is only
/// 23 hours long, so `to.difference(from).inDays` would come up one short).
int calendarDaysBetween(DateTime from, DateTime to) => DateTime.utc(
  to.year,
  to.month,
  to.day,
).difference(DateTime.utc(from.year, from.month, from.day)).inDays;
