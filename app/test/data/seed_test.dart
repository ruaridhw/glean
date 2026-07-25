// Verifies the seed data by querying a real in-memory database (AC-DATA-10),
// not by counting SQL calls — see the Expo app's
// `src/db/ingredient-categories.ts` and `src/db/seed.ts` (see git history)
// for the ported source of truth.
import 'package:glean/data/seed/taxonomy.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('seed data', () {
    late final db = createTestDatabase();

    tearDownAll(() => db.close());

    test('seeds exactly the 23-category taxonomy', () async {
      final rows = await db.select(db.ingredientCategories).get();

      expect(rows, hasLength(23));
      expect(
        rows.map((r) => r.category).toSet(),
        ingredientCategorySeeds.map((s) => s.category).toSet(),
      );
      for (final row in rows) {
        final expected = ingredientCategorySeeds.firstWhere(
          (s) => s.category == row.category,
        );
        expect(row.foodGroup, expected.foodGroup);
        expect(row.shelfLifeDays, expected.shelfLifeDays);
      }
    });

    test('seeds exactly the 10 staples, all marked isStaple', () async {
      final rows = await (db.select(
        db.ingredients,
      )..where((t) => t.isStaple.equals(true))).get();

      expect(rows, hasLength(10));
      expect(
        rows.map((r) => r.canonicalName).toSet(),
        stapleSeeds.map((s) => s.canonicalName).toSet(),
      );
      for (final row in rows) {
        final expected = stapleSeeds.firstWhere(
          (s) => s.canonicalName == row.canonicalName,
        );
        expect(row.category, expected.category);
      }
    });

    test('every staple category exists in the taxonomy', () async {
      final categories = (await db.select(db.ingredientCategories).get())
          .map((r) => r.category)
          .toSet();

      for (final staple in stapleSeeds) {
        expect(categories.contains(staple.category), isTrue);
      }
    });
  });
}
