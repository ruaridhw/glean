// Ported from the Expo app's `tests/settings/presentation.test.ts` (see
// git history) — same cases, same expected outputs, proving the port is
// behaviour-faithful.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/settings/settings_presentation.dart';

void main() {
  group('settings presentation', () {
    test('derives numeric settings options from the original model ranges', () {
      expect(buildIntegerOptions(SettingsOptionRanges.dinnersPerWeek), <int>[
        3,
        4,
        5,
        6,
        7,
      ]);
      expect(buildIntegerOptions(SettingsOptionRanges.defaultServings), <int>[
        1,
        2,
        3,
        4,
        5,
        6,
      ]);
      expect(dietaryOptions, contains('Vegetarian'));
    });

    test('formats purchase tolerance labels', () {
      expect(getToleranceLabel(0.1), 'Strict: pantry ingredients only');
      expect(getToleranceLabel(0.5), 'Moderate: minor shopping OK');
      expect(getToleranceLabel(0.9), 'Open: happy to buy new ingredients');
    });

    test('validates bounded integer input', () {
      expect(validateBoundedInteger('', 1, 7, 'Meals'), 'Meals is required');
      expect(
        validateBoundedInteger('0', 1, 7, 'Meals'),
        'Meals must be between 1 and 7',
      );
      expect(validateBoundedInteger('5', 1, 7, 'Meals'), isNull);
    });

    test('rejects non-numeric input as out of range, not a crash', () {
      expect(
        validateBoundedInteger('abc', 1, 480, 'Max active time'),
        'Max active time must be between 1 and 480',
      );
    });
  });
}
