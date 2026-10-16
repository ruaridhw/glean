/// Pure, UI-independent settings logic, shared by the Settings screen and first-run onboarding. No
/// Flutter/Riverpod import on purpose, so it is usable from a plain `dart test`.
library;

/// Dietary flags offered as toggleable chips; the order is the render order.
const List<String> dietaryOptions = <String>[
  'Vegetarian',
  'Vegan',
  'Gluten-Free',
  'Dairy-Free',
  'Tree-nut-free',
  'Peanut-free',
  'Keto',
  'Paleo',
];

/// An inclusive `[min, max]` bound for one integer setting.
class IntegerRange {
  const IntegerRange({required this.min, required this.max});

  final int min;
  final int max;
}

/// `maxActiveTimeMins` is the bound the cooking-time field must surface before it's violated, not after.
abstract final class SettingsOptionRanges {
  static const IntegerRange dinnersPerWeek = IntegerRange(min: 3, max: 7);
  static const IntegerRange defaultServings = IntegerRange(min: 1, max: 6);
  static const IntegerRange maxActiveTimeMins = IntegerRange(min: 1, max: 480);
}

/// Every integer in [range], inclusive.
List<int> buildIntegerOptions(IntegerRange range) => <int>[
  for (int value = range.min; value <= range.max; value++) value,
];

/// Human copy for the purchase-tolerance slider's current value.
String getToleranceLabel(double tolerance) {
  if (tolerance <= 0.2) return 'Strict: pantry ingredients only';
  if (tolerance <= 0.5) return 'Moderate: minor shopping OK';
  return 'Open: happy to buy new ingredients';
}

/// Validates a submitted (non-empty) integer string against `[min, max]`. An empty string is "required", not
/// "out of range": callers that treat blank as a valid "no limit" (the max active-time field) must
/// short-circuit on emptiness first.
String? validateBoundedInteger(String value, int min, int max, String label) {
  if (value.isEmpty) return '$label is required';
  final int? parsed = int.tryParse(value);
  if (parsed == null || parsed < min || parsed > max) {
    return '$label must be between $min and $max';
  }
  return null;
}
