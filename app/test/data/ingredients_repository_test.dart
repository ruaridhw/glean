// Real-outcome tests for ingredient resolution: assert what
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

    test('creates a new ingredient with the given ingredient group', () async {
      final ingredient = await repository.resolveOrCreate(
        canonicalName: 'Harissa Paste',
        groupId: 'sauces_and_condiments',
      );

      expect(ingredient.canonicalName, 'harissa paste');
      expect(ingredient.groupId, 'sauces_and_condiments');
      expect(ingredient.form, isNull, reason: 'form is never defaulted');

      // The 10 seeded staples plus this one new ingredient.
      final all = await db.select(db.ingredients).get();
      expect(all, hasLength(11));
    });

    test(
      'resolves an existing ingredient by canonical name rather than duplicating',
      () async {
        final first = await repository.resolveOrCreate(
          canonicalName: 'flour',
          groupId: 'grains',
        );
        final second = await repository.resolveOrCreate(
          canonicalName: 'Flour',
          groupId: 'grains',
        );

        expect(second.id, first.id);
        // The 10 seeded staples plus this one new ingredient.
        final all = await db.select(db.ingredients).get();
        expect(all, hasLength(11));
      },
    );

    test('resolves by catalogue item id before falling back to name', () async {
      final first = await repository.resolveOrCreate(
        canonicalName: 'tomato',
        catalogueItemId: 'tomato',
        groupId: 'tomatoes_peppers_and_aubergines',
      );
      final second = await repository.resolveOrCreate(
        canonicalName: 'different display name for the same product',
        catalogueItemId: 'tomato',
      );

      expect(second.id, first.id);
      expect(second.canonicalName, 'tomato');
    });

    test(
      'upgrades an unclassified group on an existing ingredient instead of keeping it unclassified forever',
      () async {
        // Simulates an ingredient first created via recipe import, which has
        // no group source (only the parse endpoints do).
        final fromRecipeImport = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
        );
        expect(fromRecipeImport.groupId, isNull);

        final fromPantryIntake = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
          groupId: 'sauces_and_condiments',
        );

        expect(fromPantryIntake.id, fromRecipeImport.id);
        expect(fromPantryIntake.groupId, 'sauces_and_condiments');

        final persisted = await (db.select(
          db.ingredients,
        )..where((t) => t.id.equals(fromRecipeImport.id))).getSingle();
        expect(persisted.groupId, 'sauces_and_condiments');
      },
    );

    test('never downgrades an existing classified group', () async {
      final first = await repository.resolveOrCreate(
        canonicalName: 'flour',
        groupId: 'grains',
      );

      final second = await repository.resolveOrCreate(
        canonicalName: 'flour',
        groupId: 'sauces_and_condiments',
      );

      expect(second.id, first.id);
      expect(second.groupId, 'grains');
    });

    test(
      'rejects a group the catalogue does not have via the foreign key',
      () async {
        await expectLater(
          repository.resolveOrCreate(
            canonicalName: 'mystery item',
            groupId: 'not_a_real_category',
          ),
          throwsA(anything),
        );
      },
    );

    group('canonicalUnit', () {
      test(
        'a recognised mass unit sets canonicalUnit to its base (g)',
        () async {
          final ingredient = await repository.resolveOrCreate(
            canonicalName: 'beef mince',
            groupId: 'red_meat',
            unit: 'kg',
          );

          expect(ingredient.canonicalUnit, 'g');
        },
      );

      test(
        'a recognised volume unit sets canonicalUnit to its base (ml)',
        () async {
          final ingredient = await repository.resolveOrCreate(
            canonicalName: 'whole milk',
            groupId: 'dairy',
            unit: 'l',
          );

          expect(ingredient.canonicalUnit, 'ml');
        },
      );

      test('an unrecognised, count-based unit becomes the canonical unit '
          'verbatim', () async {
        final ingredient = await repository.resolveOrCreate(
          canonicalName: 'lemon',
          groupId: 'fruit',
          unit: 'unit',
        );

        expect(ingredient.canonicalUnit, 'unit');
      });

      test('no unit given leaves canonicalUnit null', () async {
        final ingredient = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
          groupId: 'sauces_and_condiments',
        );

        expect(ingredient.canonicalUnit, isNull);
      });

      test('upgrades a null canonicalUnit on an existing ingredient instead '
          'of keeping it null forever', () async {
        // Simulates an ingredient first resolved with no unit at all
        // (recipe import never passes one — see recipes_repository.dart).
        final fromRecipeImport = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
        );
        expect(fromRecipeImport.canonicalUnit, isNull);

        final fromPantryIntake = await repository.resolveOrCreate(
          canonicalName: 'harissa paste',
          unit: 'g',
        );

        expect(fromPantryIntake.id, fromRecipeImport.id);
        expect(fromPantryIntake.canonicalUnit, 'g');

        final persisted = await (db.select(
          db.ingredients,
        )..where((t) => t.id.equals(fromRecipeImport.id))).getSingle();
        expect(persisted.canonicalUnit, 'g');
      });

      test('never changes an already-set canonicalUnit', () async {
        final first = await repository.resolveOrCreate(
          canonicalName: 'beef mince',
          unit: 'kg', // -> 'g'
        );
        expect(first.canonicalUnit, 'g');

        final second = await repository.resolveOrCreate(
          canonicalName: 'beef mince',
          unit: 'l', // would be 'ml' if this were allowed to overwrite
        );

        expect(second.id, first.id);
        expect(second.canonicalUnit, 'g');
      });
    });
  });
}
