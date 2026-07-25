// The cross-repo taxonomy contract (FLUTTER_MIGRATION.md §9). The backend's
// category -> food_group mapping (backend/src/glean/receipts/schemas.py's
// INGREDIENT_CATEGORY_FOOD_GROUPS) and this app's seed data
// (lib/data/seed/taxonomy.dart's ingredientCategorySeeds) must declare the
// same 23 categories with the same food_group for each — a silent mismatch
// here is what broke pantry grouping, meal-plan generation and expiry
// inference all at once before §9's fix. This test makes that agreement a
// build-time check rather than a "keep in sync" comment a human has to
// remember.
//
// `flutter test` always runs with the package root (`app/`) as the working
// directory, so `../backend/...` resolves regardless of which test file
// this is (mirrors test/auth/redirect_uri_contract_test.dart's equivalent
// check). Both files are parsed as text — this test never executes Python.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const String _backendPath = '../backend/src/glean/receipts/schemas.py';
const String _flutterPath = 'lib/data/seed/taxonomy.dart';

void main() {
  test('backend INGREDIENT_CATEGORY_FOOD_GROUPS ($_backendPath) agrees with '
      'ingredientCategorySeeds ($_flutterPath)', () {
    final Map<String, String> backend = _parseBackendTaxonomy(
      File(_backendPath).readAsStringSync(),
    );
    final Map<String, String> flutter = _parseFlutterTaxonomy(
      File(_flutterPath).readAsStringSync(),
    );

    // Sanity-check the parsers themselves before comparing: an empty or
    // tiny result means a regex stopped matching (e.g. the source moved to
    // a different literal style), which would otherwise show up as a
    // confusing pile of "missing" categories instead of a clear signal.
    expect(
      backend.length,
      greaterThanOrEqualTo(20),
      reason:
          'Parsed only ${backend.length} categories from $_backendPath — '
          'the parser in taxonomy_contract_test.dart likely needs updating '
          'to match that file\'s current format.',
    );
    expect(
      flutter.length,
      greaterThanOrEqualTo(20),
      reason:
          'Parsed only ${flutter.length} categories from $_flutterPath — '
          'the parser in taxonomy_contract_test.dart likely needs updating '
          'to match that file\'s current format.',
    );

    final Set<String> onlyInBackend = backend.keys.toSet().difference(
      flutter.keys.toSet(),
    );
    final Set<String> onlyInFlutter = flutter.keys.toSet().difference(
      backend.keys.toSet(),
    );

    expect(
      onlyInBackend,
      isEmpty,
      reason:
          'Categories present in $_backendPath but missing from '
          '$_flutterPath: $onlyInBackend',
    );
    expect(
      onlyInFlutter,
      isEmpty,
      reason:
          'Categories present in $_flutterPath but missing from '
          '$_backendPath: $onlyInFlutter',
    );

    final List<String> mismatches = <String>[
      for (final String category in backend.keys)
        if (backend[category] != flutter[category])
          '$category: backend food_group="${backend[category]}" vs '
              'flutter foodGroup="${flutter[category]}"',
    ];

    expect(
      mismatches,
      isEmpty,
      reason:
          'food_group mismatches between $_backendPath and $_flutterPath:\n'
          '${mismatches.join('\n')}',
    );

    expect(
      backend.length,
      23,
      reason:
          '$_backendPath declares ${backend.length} categories; the '
          'taxonomy is specified as exactly 23 (FLUTTER_MIGRATION.md §9, '
          'AC-DATA-10).',
    );
  });
}

/// Extracts `{"category": "food_group", ...}` entries from the
/// `INGREDIENT_CATEGORY_FOOD_GROUPS` dict literal in [source].
Map<String, String> _parseBackendTaxonomy(String source) {
  const String marker = 'INGREDIENT_CATEGORY_FOOD_GROUPS';
  final int markerIndex = source.indexOf(marker);
  expect(
    markerIndex,
    greaterThanOrEqualTo(0),
    reason: '$marker not found in $_backendPath — has it been renamed?',
  );
  final int braceStart = source.indexOf('{', markerIndex);
  final int braceEnd = source.indexOf('}', braceStart);
  final String block = source.substring(braceStart, braceEnd);

  final RegExp entry = RegExp('"([a-z_]+)"\\s*:\\s*"([a-z]+)"');
  return <String, String>{
    for (final RegExpMatch match in entry.allMatches(block))
      match.group(1)!: match.group(2)!,
  };
}

/// Extracts `CategorySeed('category', 'food_group', shelfLifeDays)` entries
/// from the `ingredientCategorySeeds` list literal in [source].
Map<String, String> _parseFlutterTaxonomy(String source) {
  const String marker = 'ingredientCategorySeeds';
  final int markerIndex = source.indexOf(marker);
  expect(
    markerIndex,
    greaterThanOrEqualTo(0),
    reason: '$marker not found in $_flutterPath — has it been renamed?',
  );
  final int bracketStart = source.indexOf('[', markerIndex);
  final int bracketEnd = source.indexOf(']', bracketStart);
  final String block = source.substring(bracketStart, bracketEnd);

  final RegExp entry = RegExp(
    "CategorySeed\\('([a-z_]+)',\\s*'([a-z]+)',\\s*\\d+\\)",
  );
  return <String, String>{
    for (final RegExpMatch match in entry.allMatches(block))
      match.group(1)!: match.group(2)!,
  };
}
