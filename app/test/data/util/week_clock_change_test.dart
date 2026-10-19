import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/viewed_plan_week.dart';
import 'package:glean/data/util/week.dart';

// A week must start at local Monday 00:00 whatever the clock does. These dates are the weeks around the UK clock
// changes of 2026 (29 March, 25 October); the assertions bite when the suite runs with TZ=Europe/London (see
// flutter-ci.yml) and hold trivially in a zone without daylight saving.
void main() {
  // [Monday of the week before the change, Monday of the change week, Monday after].
  final clockChanges = {
    'spring forward (29 Mar 2026)': [
      DateTime(2026, 3, 23),
      DateTime(2026, 3, 30),
      DateTime(2026, 4, 6),
    ],
    'fall back (25 Oct 2026)': [
      DateTime(2026, 10, 19),
      DateTime(2026, 10, 26),
      DateTime(2026, 11, 2),
    ],
  };

  for (final MapEntry(key: name, value: [before, during, after])
      in clockChanges.entries) {
    group(name, () {
      test('endOfWeek is the next local Monday midnight', () {
        expect(endOfWeek(before), during);
        expect(endOfWeek(during), after);
      });

      test('shiftWeeks pages forward and back between Mondays', () {
        expect(shiftWeeks(before, 1), during);
        expect(shiftWeeks(during, 1), after);
        expect(shiftWeeks(after, -1), during);
        expect(shiftWeeks(during, -1), before);
      });

      test('every day of the week resolves to its Monday', () {
        for (final DateTime monday in [before, during]) {
          for (var i = 0; i < 7; i++) {
            final day = addDays(monday, i);
            expect(startOfWeek(day), monday, reason: '$day');
            final lateEvening = DateTime(day.year, day.month, day.day, 23, 30);
            expect(startOfWeek(lateEvening), monday, reason: '$lateEvening');
          }
        }
      });

      test('the viewed week advances and retreats across the change', () {
        final container = ProviderContainer(
          overrides: [clockProvider.overrideWithValue(() => before)],
        );
        addTearDown(container.dispose);
        final notifier = container.read(viewedPlanWeekProvider.notifier);
        expect(container.read(viewedPlanWeekProvider), before);

        notifier.select(shiftWeeks(container.read(viewedPlanWeekProvider), 1));
        expect(container.read(viewedPlanWeekProvider), during);
        notifier.select(shiftWeeks(container.read(viewedPlanWeekProvider), 1));
        expect(container.read(viewedPlanWeekProvider), after);
        notifier.select(shiftWeeks(container.read(viewedPlanWeekProvider), -1));
        notifier.select(shiftWeeks(container.read(viewedPlanWeekProvider), -1));
        expect(container.read(viewedPlanWeekProvider), before);
      });
    });
  }

  group('calendar days', () {
    test('addDays lands on local midnight whatever the time of day', () {
      expect(addDays(DateTime(2026, 3, 28, 23, 30), 2), DateTime(2026, 3, 30));
      expect(addDays(DateTime(2026, 10, 24, 12), 2), DateTime(2026, 10, 26));
    });

    test('calendarDaysBetween counts dates, not elapsed hours', () {
      expect(
        calendarDaysBetween(DateTime(2026, 3, 28), DateTime(2026, 3, 30)),
        2,
      );
      expect(
        calendarDaysBetween(
          DateTime(2026, 3, 28, 22),
          DateTime(2026, 3, 30, 1),
        ),
        2,
      );
      expect(
        calendarDaysBetween(DateTime(2026, 10, 24), DateTime(2026, 10, 26)),
        2,
      );
      expect(
        calendarDaysBetween(DateTime(2026, 10, 26), DateTime(2026, 10, 24)),
        -2,
      );
    });
  });
}
