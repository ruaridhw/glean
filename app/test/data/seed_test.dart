// Verifies the seed data by querying a real in-memory database, not by counting SQL calls.
import 'package:glean/data/seed/ingredient_groups.dart';
import 'package:glean/data/seed/taxonomy.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('seed data', () {
    late final db = createTestDatabase();

    tearDownAll(() => db.close());

    test('seeds exactly the 29 ingredient groups', () async {
      final rows = await db.select(db.ingredientGroups).get();

      expect(rows, hasLength(29));
      expect(
        rows.map((r) => r.id).toSet(),
        ingredientGroupSeeds.map((s) => s.id).toSet(),
      );
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
        expect(row.groupId, expected.groupId);
      }
    });

    test('every staple names an ingredient group the app seeds', () async {
      final groups = (await db.select(db.ingredientGroups).get())
          .map((r) => r.id)
          .toSet();

      for (final staple in stapleSeeds) {
        expect(groups.contains(staple.groupId), isTrue);
      }
    });
  });
}
