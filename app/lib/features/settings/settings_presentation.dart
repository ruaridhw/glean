/// Pure, UI-independent settings logic — ported 1:1 from
/// `mobile/src/settings/presentation.ts` (kept, per IMPLEMENTATION.md, as
/// "presentation logic that ports as unit-testable functions; it has a real
/// test worth keeping"). No Flutter/Riverpod import here on purpose: this
/// file is usable from a plain `dart test` as well as from both the Settings
/// screen and the first-run onboarding flow, which share these controls
/// (FLUTTER_MIGRATION.md §6 — "reuse the same controls as Settings rather
/// than duplicating them").
library;

/// Dietary flags offered as toggleable chips. Mirrors RN's `DIETARY_OPTIONS`
/// verbatim (order matters — it's the order chips render in).
const List<String> dietaryOptions = <String>[
  'Vegetarian',
  'Vegan',
  'Gluten-Free',
  'Dairy-Free',
  'Nut-Free',
  'Keto',
  'Paleo',
];

/// An inclusive `[min, max]` bound for one integer setting.
class IntegerRange {
  const IntegerRange({required this.min, required this.max});

  final int min;
  final int max;
}

/// Mirrors RN's `SETTINGS_OPTION_RANGES`. `maxActiveTimeMins` is the bound
/// AC-UX-05 requires the cooking-time field to surface *before* it's
/// violated, not after.
abstract final class SettingsOptionRanges {
  static const IntegerRange dinnersPerWeek = IntegerRange(min: 3, max: 7);
  static const IntegerRange defaultServings = IntegerRange(min: 1, max: 6);
  static const IntegerRange maxActiveTimeMins = IntegerRange(min: 1, max: 480);
}

/// Every integer in [range], inclusive. Mirrors RN's `buildIntegerOptions`.
List<int> buildIntegerOptions(IntegerRange range) => <int>[
  for (int value = range.min; value <= range.max; value++) value,
];

/// Human copy for the purchase-tolerance slider's current value. Mirrors
/// RN's `getToleranceLabel` thresholds exactly.
String getToleranceLabel(double tolerance) {
  if (tolerance <= 0.2) return 'Strict: pantry ingredients only';
  if (tolerance <= 0.5) return 'Moderate: minor shopping OK';
  return 'Open: happy to buy new ingredients';
}

/// Validates a submitted (non-empty) integer string against `[min, max]`.
/// Mirrors RN's `validateBoundedInteger`: an empty string is "required", not
/// "out of range" — callers that treat blank as a valid "no limit" (the max
/// active-time field) must short-circuit on emptiness themselves before
/// calling this, exactly as the RN screen did.
String? validateBoundedInteger(String value, int min, int max, String label) {
  if (value.isEmpty) return '$label is required';
  final int? parsed = int.tryParse(value);
  if (parsed == null || parsed < min || parsed > max) {
    return '$label must be between $min and $max';
  }
  return null;
}
