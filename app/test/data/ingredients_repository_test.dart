// Real-outcome tests for ingredient resolution (AC-TEST-02): assert what
// ends up in the ingredients table, never how many times a query method
// was called.
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('IngredientsRepository.resolveOrCreate', () {
    late GleanDatabase db;
    late IngredientsRepository repository;

    setUp(() {
      db = createTestDatabase();
      repository = IngredientsRepository(db);
    });

    tearDown(() => db.close());

    test('creates a new ingredient with the given category', () async {
      final ingredient = await repository.resolveOrCreate(
        canonicalName: 'Harissa Paste',
        category: 'condiments',
      );

      expect(ingredient.canonicalName, 'harissa paste');
      expect(ingredient.category, 'condiments');

      // The 10 seeded staples (AC-DATA-10) plus this one new ingredient.
      final all = await db.select(db.ingredients).get();
      expect(all, hasLength(11));
    });

    test(
      'resolves an existing ingredient by canonical name rather than duplicating',
      () async {
        final first = await repository.resolveOrCreate(
          canonicalName: 'flour',
          category: 'grains',
        );
        final second = await repository.resolveOrCreate(
          canonicalName: 'Flour',
          category: 'grains',
        );

        expect(second.id, first.id);
        // The 10 seeded staples (AC-DATA-10) plus this one new ingredient.
        final all = await db.select(db.ingredients).get();
        expect(all, hasLength(11));
      },
    );

    test('resolves by api ingredient id before falling back to name', () async {
      final first = await repository.resolveOrCreate(
        canonicalName: 'tomato',
        apiIngredientId: 'api-123',
        category: 'nightshades',
      );
      final second = await repository.resolveOrCreate(
        canonicalName: 'different display name for the same product',
        apiIngredientId: 'api-123',
      );

      expect(second.id, first.id);
      expect(second.canonicalName, 'tomato');
    });

    test(
      'upgrades a null category on an existing ingredient instead of keeping it null forever',
      () async {
        // Simulates an ingredient first created via recipe import, which has
        // no category source (only the parse endpoints do, §9).
        final fromRecipeImport = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
        );
        expect(fromRecipeImport.category, isNull);

        final fromPantryIntake = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
          category: 'condiments',
        );

        expect(fromPantryIntake.id, fromRecipeImport.id);
        expect(fromPantryIntake.category, 'condiments');

        final persisted = await (db.select(
          db.ingredients,
        )..where((t) => t.id.equals(fromRecipeImport.id))).getSingle();
        expect(persisted.category, 'condiments');
      },
    );

    test('never downgrades an existing non-null category', () async {
      final first = await repository.resolveOrCreate(
        canonicalName: 'flour',
        category: 'grains',
      );

      final second = await repository.resolveOrCreate(
        canonicalName: 'flour',
        category: 'condiments',
      );

      expect(second.id, first.id);
      expect(second.category, 'grains');
    });

    test(
      'rejects a category outside the taxonomy via the foreign key',
      () async {
        await expectLater(
          repository.resolveOrCreate(
            canonicalName: 'mystery item',
            category: 'not_a_real_category',
          ),
          throwsA(anything),
        );
      },
    );
  });
}
