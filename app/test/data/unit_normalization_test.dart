// Real-outcome tests for `normalizeUnit`/`canonicalUnitFor` (AC-TEST-05).
//
// Ported from the Expo app's `src/normalization/units.ts` test suite
// (`git show 906c9bb^:mobile/src/__tests__/normalization/units.test.ts`) —
// this file previously had **no test at all** (FINDINGS.md R-22), which is
// the direct reason R-18's normalisation-never-fires defect went unnoticed:
// nothing exercised `normalizeUnit` in isolation, so a `canonicalUnit` that
// was always null never tripped anything here.
import 'package:glean/data/util/unit_normalization.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('normalizeUnit', () {
    test('returns identity when unit matches canonicalUnit', () {
      final result = normalizeUnit(
        quantity: 500,
        unit: 'g',
        canonicalUnit: 'g',
        canonicalName: 'chicken breast',
      );
      expect(result?.quantity, 500);
      expect(result?.unit, 'g');
      expect(result?.source, NormalizeSource.identity);
    });

    test('returns identity when canonicalUnit is null', () {
      final result = normalizeUnit(
        quantity: 2,
        unit: 'units',
        canonicalUnit: null,
        canonicalName: 'egg',
      );
      expect(result?.quantity, 2);
      expect(result?.unit, 'units');
      expect(result?.source, NormalizeSource.identity);
    });

    test('converts kg -> g', () {
      final result = normalizeUnit(
        quantity: 0.5,
        unit: 'kg',
        canonicalUnit: 'g',
        canonicalName: 'beef mince',
      );
      expect(result?.quantity, closeTo(500, 0.1));
      expect(result?.unit, 'g');
      expect(result?.source, NormalizeSource.lookup);
    });

    test('converts L -> ml', () {
      final result = normalizeUnit(
        quantity: 1.5,
        unit: 'l',
        canonicalUnit: 'ml',
        canonicalName: 'whole milk',
      );
      expect(result?.quantity, closeTo(1500, 0.1));
      expect(result?.unit, 'ml');
      expect(result?.source, NormalizeSource.lookup);
    });

    test('converts cup of flour -> g via density', () {
      final result = normalizeUnit(
        quantity: 1,
        unit: 'cup',
        canonicalUnit: 'g',
        canonicalName: 'plain flour',
      );
      // 1 cup = 236.588ml x 0.593 g/ml ~= 140.3g
      expect(result?.quantity, closeTo(140.3, 0.5));
      expect(result?.unit, 'g');
      expect(result?.source, NormalizeSource.density);
    });

    test('converts kg of milk -> ml via density (reverse direction)', () {
      // The reverse of the cup-of-flour case: a mass source unit converting
      // into a volume canonical unit. Not in the original suite, but the
      // reverse branch (`conv.to == 'g' && canonicalUnit == 'ml'`) has no
      // other coverage otherwise.
      final result = normalizeUnit(
        quantity: 103,
        unit: 'kg',
        canonicalUnit: 'ml',
        canonicalName: 'milk',
      );
      // 103kg -> 103000g / 1.03 g per ml = 100000ml.
      expect(result?.quantity, closeTo(100000, 1));
      expect(result?.unit, 'ml');
      expect(result?.source, NormalizeSource.density);
    });

    test('base ml converts to g using a known density', () {
      final result = normalizeUnit(
        quantity: 500,
        unit: 'ml',
        canonicalUnit: 'g',
        canonicalName: 'milk',
      );
      expect(result?.quantity, 515);
      expect(result?.unit, 'g');
    });

    test('base g converts to ml using a known density', () {
      final result = normalizeUnit(
        quantity: 515,
        unit: 'g',
        canonicalUnit: 'ml',
        canonicalName: 'milk',
      );
      expect(result?.quantity, closeTo(500, 1e-9));
      expect(result?.unit, 'ml');
    });

    test('returns null for unknown ambiguous conversion', () {
      final result = normalizeUnit(
        quantity: 1,
        unit: 'head',
        canonicalUnit: 'units',
        canonicalName: 'garlic',
      );
      expect(result, isNull);
    });

    test('returns null when a volume/mass unit has no density entry for the '
        'ingredient', () {
      // 'saffron' has no row in the density table, so a volume->mass
      // conversion has nothing to fall back on — must fail rather than
      // guess, since a wrong density would silently corrupt the quantity
      // (exactly the class of bug R-18 exists to prevent).
      final result = normalizeUnit(
        quantity: 1,
        unit: 'tsp',
        canonicalUnit: 'g',
        canonicalName: 'saffron',
      );
      expect(result, isNull);
    });

    test('unit comparison is case- and whitespace-insensitive', () {
      final result = normalizeUnit(
        quantity: 2,
        unit: ' KG ',
        canonicalUnit: 'g',
        canonicalName: 'beef mince',
      );
      expect(result?.quantity, closeTo(2000, 0.1));
      expect(result?.unit, 'g');
      expect(result?.source, NormalizeSource.lookup);
    });
  });

  group('canonicalUnitFor', () {
    test('resolves a recognised mass unit to its base (g)', () {
      expect(canonicalUnitFor('kg'), 'g');
      expect(canonicalUnitFor('lbs'), 'g');
    });

    test('resolves a recognised volume unit to its base (ml)', () {
      expect(canonicalUnitFor('l'), 'ml');
      expect(canonicalUnitFor('cup'), 'ml');
    });

    test('is case- and whitespace-insensitive', () {
      expect(canonicalUnitFor(' KG '), 'g');
    });

    test('falls back to the normalised raw unit for an unrecognised, typically '
        'count-based unit', () {
      expect(canonicalUnitFor('units'), 'units');
      expect(canonicalUnitFor('Clove'), 'clove');
    });
  });
}
