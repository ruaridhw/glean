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

    group('with a synced catalogue', () {
      Future<void> syncOnion() async {
        await db.batch((b) {
          b.insert(
            db.catalogueItems,
            CatalogueItemsCompanion.insert(
              id: 'onion',
              name: 'onion',
              groupId: 'onions_and_garlic',
              form: 'fresh',
              source: 'seed',
            ),
          );
          b.insert(
            db.catalogueItems,
            CatalogueItemsCompanion.insert(
              id: 'shallot',
              name: 'shallot',
              groupId: 'onions_and_garlic',
              form: 'fresh',
              source: 'seed',
            ),
          );
          b.insertAll(db.catalogueAliases, [
            for (final name in ['onion', 'brown onion', 'onions'])
              CatalogueAliasesCompanion.insert(
                key: name,
                name: name,
                itemId: 'onion',
              ),
            CatalogueAliasesCompanion.insert(
              key: 'shallot',
              name: 'shallot',
              itemId: 'shallot',
            ),
            CatalogueAliasesCompanion.insert(
              key: 'banana shallot',
              name: 'banana shallot',
              itemId: 'old-shallot',
            ),
          ]);
          b.insert(
            db.catalogueItemRedirects,
            CatalogueItemRedirectsCompanion.insert(
              formerId: 'old-shallot',
              itemId: 'shallot',
            ),
          );
        });
      }

      test('a known alias resolves to the ingredient already linked to its '
          'item instead of creating a second one', () async {
        final onion = await repository.resolveOrCreate(
          canonicalName: 'onion',
          groupId: 'onions_and_garlic',
        );
        await syncOnion();
        await db.linkIngredientsToCatalogue();

        final brown = await repository.resolveOrCreate(
          canonicalName: 'Brown Onion',
        );

        expect(brown.id, onion.id);
        expect(
          (await db.select(db.ingredients).get()).where(
            (i) => i.catalogueItemId == 'onion',
          ),
          hasLength(1),
        );
      });

      test('an alias of a merged item resolves through the redirect', () async {
        await syncOnion();
        final first = await repository.resolveOrCreate(
          canonicalName: 'banana shallot',
        );
        final second = await repository.resolveOrCreate(
          canonicalName: 'shallot',
        );

        expect(first.catalogueItemId, 'shallot');
        expect(second.id, first.id);
      });

      test('a known name with no ingredient yet creates one linked to its '
          'item, with no form', () async {
        await syncOnion();

        final created = await repository.resolveOrCreate(
          canonicalName: 'onions',
        );

        expect(created.canonicalName, 'onions');
        expect(created.catalogueItemId, 'onion');
        expect(created.form, isNull);
      });

      test('an existing row for the exact name is linked and reused, not '
          'duplicated', () async {
        final before = await repository.resolveOrCreate(
          canonicalName: 'onions',
        );
        await syncOnion();

        final after = await repository.resolveOrCreate(canonicalName: 'onions');

        expect(after.id, before.id);
        expect(after.catalogueItemId, 'onion');
      });

      test('resolving a catalogue id that several existing ingredients share '
          'picks the oldest one, every time, and never throws', () async {
        final oldest = await repository.resolveOrCreate(canonicalName: 'onion');
        final newer = await repository.resolveOrCreate(
          canonicalName: 'brown onion',
        );
        await syncOnion();
        await db.linkIngredientsToCatalogue();
        // Both pre-existing rows now carry the item.
        expect(
          (await db.select(db.ingredients).get())
              .where((i) => i.catalogueItemId == 'onion')
              .map((i) => i.id),
          unorderedEquals([oldest.id, newer.id]),
        );

        for (var i = 0; i < 2; i++) {
          final byId = await repository.resolveOrCreate(
            canonicalName: 'anything',
            catalogueItemId: 'onion',
          );
          expect(byId.id, oldest.id);
          final byAlias = await repository.resolveOrCreate(
            canonicalName: 'onions',
          );
          expect(byAlias.id, oldest.id);
        }
      });
    });
  });
}
