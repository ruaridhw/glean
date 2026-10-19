// Real-outcome tests for pantry reads/writes, including automatic expiry
// inference and a guaranteed non-null `foodGroup` on every row.
import 'package:drift/drift.dart' show Value;
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('PantryRepository', () {
    late GleanDatabase db;
    late PantryRepository repository;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      repository = PantryRepository(db, IngredientsRepository(db));
    });

    tearDown(() => db.close());

    test(
      'addItem infers an expiry date from the ingredient group\'s shelf life',
      () async {
        final now = DateTime(2026, 1, 1);
        await repository.addItem(
          userId: userId,
          name: 'strawberries',
          quantity: 1,
          unit: 'punnet',
          groupId: 'fruit', // 7-day fresh shelf life
          now: now,
        );

        final items = await repository.watchAll(userId).first;
        expect(items, hasLength(1));
        expect(items.single.expiryDate, DateTime(2026, 1, 8));
      },
    );

    test(
      'an ingredient with no ingredient group, or in Other, gets no inferred '
      'expiry',
      () async {
        for (final groupId in <String?>[null, 'other']) {
          await repository.addItem(
            userId: userId,
            name: 'mystery $groupId',
            quantity: 1,
            unit: 'unit',
            groupId: groupId,
            now: DateTime(2026, 1, 1),
          );
        }

        final items = await repository.watchAll(userId).first;
        expect(items.map((i) => i.expiryDate), [null, null]);
        expect(items.map((i) => i.shelfLifeDays), [null, null]);
      },
    );

    test('a group that never expires gets no inferred expiry, and one with a '
        'single shelf life uses it', () async {
      await repository.addItem(
        userId: userId,
        name: 'washing-up liquid',
        quantity: 1,
        unit: 'unit',
        groupId: 'household',
        now: DateTime(2026, 1, 1),
      );
      await repository.addItem(
        userId: userId,
        name: 'sourdough',
        quantity: 1,
        unit: 'unit',
        groupId: 'bread',
        now: DateTime(2026, 1, 1),
      );

      final byName = {
        for (final i in await repository.watchAll(userId).first)
          i.canonicalName: i,
      };
      expect(byName['washing-up liquid']!.expiryDate, isNull);
      expect(byName['sourdough']!.expiryDate, DateTime(2026, 1, 6));
    });

    test('an ingredient with no stated form is not given one, and beans and '
        'pulses keep the dry-stock shelf life they always had', () async {
      final id = await repository.addItem(
        userId: userId,
        name: 'lentils',
        quantity: 500,
        unit: 'g',
        groupId: 'beans_and_pulses',
        now: DateTime(2026, 1, 1),
      );

      final item = (await repository.watchAll(userId).first).single;
      expect(item.expiryDate, DateTime(2026, 6, 30));
      expect(
        (await (db.select(
          db.ingredients,
        )..where((t) => t.id.equals(id))).getSingle()).form,
        isNull,
      );
    });

    test('a linked ingredient takes its shelf life from the catalogue item, '
        'household override included', () async {
      await db
          .into(db.catalogueItems)
          .insert(
            CatalogueItemsCompanion.insert(
              id: 'strawberries',
              name: 'strawberries',
              groupId: 'fruit',
              form: 'fresh',
              source: 'seed',
            ),
          );
      await db
          .into(db.catalogueAliases)
          .insert(
            CatalogueAliasesCompanion.insert(
              key: 'strawberries',
              name: 'strawberries',
              itemId: 'strawberries',
            ),
          );
      await db
          .into(db.ingredientOverrides)
          .insert(
            IngredientOverridesCompanion.insert(
              itemId: 'strawberries',
              unopenedShelfLifeDays: const Value(3),
            ),
          );

      await repository.addItem(
        userId: userId,
        name: 'strawberries',
        quantity: 1,
        unit: 'punnet',
        groupId: 'fruit',
        now: DateTime(2026, 1, 1),
      );

      final item = (await repository.watchAll(userId).first).single;
      expect(item.expiryDate, DateTime(2026, 1, 4));
      expect(item.shelfLifeDays, 3);
    });

    test('the persisted group survives — food_group is never null', () async {
      await repository.addItem(
        userId: userId,
        name: 'aubergine',
        quantity: 2,
        unit: 'unit',
        groupId: 'tomatoes_peppers_and_aubergines',
        now: DateTime(2026, 1, 1),
      );

      final items = await repository.watchAll(userId).first;
      expect(items.single.groupId, 'tomatoes_peppers_and_aubergines');
      expect(items.single.foodGroup, 'vegetables');
    });

    test(
      'a pantry item whose ingredient has no ingredient group still appears, with foodGroup "other" (regression)',
      () async {
        // Simulates an ingredient that reached the pantry with no
        // ingredient group at all — e.g. one first created by recipe import
        // (which has no ingredient group source) and never since resolved
        // through a categorised pantry/shopping intake path. `addItem`
        // itself always supplies a group, so this bypasses it
        // deliberately, the same way a future insert path that forgets to
        // would.
        final ingredients = IngredientsRepository(db);
        final ingredient = await ingredients.resolveOrCreate(
          canonicalName: 'mystery meat',
        );
        expect(ingredient.groupId, isNull);
        await db
            .into(db.pantryItems)
            .insert(
              PantryItemsCompanion.insert(
                userId: userId,
                ingredientId: ingredient.id,
                quantity: 1,
                unit: 'unit',
                updatedAt: DateTime(2026, 1, 1).toIso8601String(),
              ),
            );

        final items = await repository.watchAll(userId).first;

        // The item must still be visible — disappearing entirely would be
        // silent data loss, strictly worse than the RN app's "Other"
        // bucket (the Expo app's `src/pantry/presentation.ts:47`, see git
        // history).
        expect(items, hasLength(1));
        expect(items.single.canonicalName, 'mystery meat');
        expect(items.single.groupId, isNull);
        expect(items.single.foodGroup, 'other');
        expect(items.single.shelfLifeDays, isNull);
      },
    );

    test(
      'topping up an existing item adds to the quantity and refreshes expiry',
      () async {
        await repository.addItem(
          userId: userId,
          name: 'milk',
          quantity: 500,
          unit: 'ml',
          groupId: 'dairy',
          now: DateTime(2026, 1, 1),
        );
        await repository.addItem(
          userId: userId,
          name: 'milk',
          quantity: 500,
          unit: 'ml',
          groupId: 'dairy',
          now: DateTime(2026, 1, 3),
        );

        final items = await repository.watchAll(userId).first;
        expect(items, hasLength(1));
        expect(items.single.quantity, 1000);
        expect(
          items.single.expiryDate,
          DateTime(2026, 1, 10),
        ); // 7-day dairy shelf life from the second add
      },
    );

    test(
      'addItem normalizes units into the ingredient canonical unit '
      '(even the very first add, which is also what sets the target)',
      () async {
        // 'plain flour' is a seeded staple with no canonicalUnit yet. This
        // first add both establishes it (as 'g', derived from 'kg' — see
        // `IngredientsRepository.resolveOrCreate`) and is itself normalized
        // into it in the same call, rather than being stored as raw kg.
        await repository.addItem(
          userId: userId,
          name: 'plain flour',
          quantity: 1,
          unit: 'kg',
          groupId: 'grains',
          now: DateTime(2026, 1, 1),
        );

        final items = await repository.watchAll(userId).first;
        expect(items.single.unit, 'g');
        expect(items.single.quantity, 1000);
      },
    );

    test('a mixed-unit top-up converts and sums correctly instead of '
        'corrupting the quantity', () async {
      // "2 kg flour" then "500 g flour" must total 2500g, never "502 kg".
      await repository.addItem(
        userId: userId,
        name: 'plain flour',
        quantity: 2,
        unit: 'kg',
        groupId: 'grains',
        now: DateTime(2026, 1, 1),
      );
      await repository.addItem(
        userId: userId,
        name: 'plain flour',
        quantity: 500,
        unit: 'g',
        groupId: 'grains',
        now: DateTime(2026, 1, 3),
      );

      final items = await repository.watchAll(userId).first;
      expect(items, hasLength(1));
      expect(items.single.unit, 'g');
      expect(items.single.quantity, 2500);
    });

    test('a genuinely incompatible unit merge throws rather than silently '
        'summing under the wrong unit', () async {
      // First add establishes 'units' as garlic's canonical unit (not a
      // recognised mass/volume unit, so it becomes the literal unit).
      await repository.addItem(
        userId: userId,
        name: 'garlic',
        quantity: 3,
        unit: 'units',
        groupId: 'onions_and_garlic',
        now: DateTime(2026, 1, 1),
      );

      // A later add in a mass unit has no conversion path to 'units' and
      // no density entry either — must fail loudly, not sum 3 + 50 under
      // 'units'.
      await expectLater(
        repository.addItem(
          userId: userId,
          name: 'garlic',
          quantity: 50,
          unit: 'g',
          groupId: 'onions_and_garlic',
          now: DateTime(2026, 1, 2),
        ),
        throwsA(isA<PantryUnitMismatchException>()),
      );

      // The original row must survive untouched — the whole point of
      // failing loudly instead of merging.
      final items = await repository.watchAll(userId).first;
      expect(items.single.quantity, 3);
      expect(items.single.unit, 'units');
    });

    test('a blank unit defaults to "units" for the row, but never seeds the '
        "ingredient's shared canonical unit — a later, explicit add (even "
        'from another user, since the ingredient catalog is shared) still '
        'can', () async {
      final ingredients = IngredientsRepository(db);

      // The review screen's exact scenario: the unit field was left
      // blank (e.g. the user cleared it), not a real chosen unit.
      await repository.addItem(
        userId: 'user-a',
        name: 'chia seeds',
        quantity: 1,
        unit: '',
        groupId: 'grains',
        now: DateTime(2026, 1, 1),
      );

      final itemsA = await repository.watchAll('user-a').first;
      // The row itself still needs *some* unit to store and display.
      expect(itemsA.single.unit, 'units');

      // But the shared ingredient's canonical unit was never seeded from
      // that fallback — it must still be null, i.e. unresolved, not
      // permanently locked to 'units'.
      var ingredient = await ingredients.resolveOrCreate(
        canonicalName: 'chia seeds',
      );
      expect(ingredient.canonicalUnit, isNull);

      // A later, genuinely explicit unit — even from a different user,
      // since `ingredients` is a shared, non-user-scoped catalog — is
      // free to seed it. This would throw a `PantryUnitMismatchException`
      // instead if the earlier blank had already claimed 'units'.
      await repository.addItem(
        userId: 'user-b',
        name: 'chia seeds',
        quantity: 200,
        unit: 'g',
        groupId: 'grains',
        now: DateTime(2026, 1, 2),
      );

      ingredient = await ingredients.resolveOrCreate(
        canonicalName: 'chia seeds',
      );
      expect(ingredient.canonicalUnit, 'g');
    });

    test('updateItem changes only the fields provided', () async {
      final now = DateTime(2026, 1, 1);
      await repository.addItem(
        userId: userId,
        name: 'butter',
        quantity: 250,
        unit: 'g',
        groupId: 'dairy',
        now: now,
      );
      final before = (await repository.watchAll(userId).first).single;

      await repository.updateItem(
        id: before.id,
        userId: userId,
        quantity: 100,
        now: now,
      );

      final after = (await repository.watchAll(userId).first).single;
      expect(after.quantity, 100);
      expect(after.unit, before.unit);
      expect(after.expiryDate, before.expiryDate);
    });

    test('deleteItem removes the row', () async {
      await repository.addItem(
        userId: userId,
        name: 'eggs',
        quantity: 6,
        unit: 'unit',
        groupId: 'eggs',
        now: DateTime(2026, 1, 1),
      );
      final item = (await repository.watchAll(userId).first).single;

      await repository.deleteItem(id: item.id, userId: userId);

      expect(await repository.watchAll(userId).first, isEmpty);
    });

    group('decrementForCook / restoreFromCook', () {
      test(
        'reverses a decrement exactly, restoring quantity and lastUsedAt',
        () async {
          final addedAt = DateTime(2026, 1, 1);
          await repository.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 500,
            unit: 'g',
            groupId: 'poultry',
            now: addedAt,
          );
          final before = (await repository.watchAll(userId).first).single;
          expect(before.lastUsedAt, isNull);

          final cookedAt = DateTime(2026, 1, 2);
          final delta = await repository.decrementForCook(
            userId: userId,
            ingredientId: before.ingredientId,
            amount: 200,
            now: cookedAt,
          );
          expect(delta, isNotNull);
          expect(delta!.amountApplied, 200);
          expect(delta.previousLastUsedAt, isNull);

          final afterCook = (await repository.watchAll(userId).first).single;
          expect(afterCook.quantity, 300);
          expect(afterCook.lastUsedAt, cookedAt);

          await repository.restoreFromCook(
            userId: userId,
            ingredientId: before.ingredientId,
            amount: delta.amountApplied,
            unit: delta.unit,
            previousLastUsedAt: delta.previousLastUsedAt,
            now: DateTime(2026, 1, 3),
          );

          final restored = (await repository.watchAll(userId).first).single;
          expect(restored.quantity, before.quantity);
          expect(restored.lastUsedAt, before.lastUsedAt);
        },
      );

      test(
        'floors the decrement at the available quantity, not the requested amount',
        () async {
          await repository.addItem(
            userId: userId,
            name: 'rice',
            quantity: 100,
            unit: 'g',
            groupId: 'pasta_and_rice',
            now: DateTime(2026, 1, 1),
          );
          final before = (await repository.watchAll(userId).first).single;

          final delta = await repository.decrementForCook(
            userId: userId,
            ingredientId: before.ingredientId,
            amount: 300, // more than is in the pantry
            now: DateTime(2026, 1, 2),
          );

          expect(delta!.amountApplied, 100); // floored, not 300
          final after = (await repository.watchAll(userId).first).single;
          expect(after.quantity, 0);
        },
      );

      test(
        'returns null when there is no pantry row for the ingredient',
        () async {
          final ingredient = await IngredientsRepository(
            db,
          ).resolveOrCreate(canonicalName: 'saffron', groupId: 'spices');

          final delta = await repository.decrementForCook(
            userId: userId,
            ingredientId: ingredient.id,
            amount: 1,
            now: DateTime(2026, 1, 1),
          );

          expect(delta, isNull);
        },
      );
    });

    group('getAll (one-shot snapshot)', () {
      test('matches watchAll\'s rows for the same user', () async {
        await repository.addItem(
          userId: userId,
          name: 'strawberries',
          quantity: 1,
          unit: 'punnet',
          groupId: 'fruit',
          now: DateTime(2026, 1, 1),
        );

        final snapshot = await repository.getAll(userId);
        expect(snapshot, hasLength(1));
        expect(snapshot.single.canonicalName, 'strawberries');
        expect(snapshot.single.foodGroup, 'fruit');
      });

      test(
        'a pantry item whose ingredient has no ingredient group still appears, '
        'with foodGroup "other" (regression, same join shape as watchAll)',
        () async {
          final ingredients = IngredientsRepository(db);
          final ingredient = await ingredients.resolveOrCreate(
            canonicalName: 'mystery meat',
          );
          expect(ingredient.groupId, isNull);
          await db
              .into(db.pantryItems)
              .insert(
                PantryItemsCompanion.insert(
                  userId: userId,
                  ingredientId: ingredient.id,
                  quantity: 1,
                  unit: 'unit',
                  updatedAt: DateTime(2026, 1, 1).toIso8601String(),
                ),
              );

          final snapshot = await repository.getAll(userId);

          // Same non-dropping guarantee as watchAll's leftOuterJoin — a
          // unclassified ingredient must never disappear the row (data-loss bug
          // already fixed once for the stream version).
          expect(snapshot, hasLength(1));
          expect(snapshot.single.canonicalName, 'mystery meat');
          expect(snapshot.single.groupId, isNull);
          expect(snapshot.single.foodGroup, 'other');
          expect(snapshot.single.shelfLifeDays, isNull);
        },
      );

      test('only returns the given user\'s items', () async {
        await repository.addItem(
          userId: userId,
          name: 'garlic',
          quantity: 1,
          unit: 'unit',
          groupId: 'onions_and_garlic',
          now: DateTime(2026, 1, 1),
        );
        await repository.addItem(
          userId: 'user-b',
          name: 'ginger',
          quantity: 1,
          unit: 'unit',
          groupId: 'onions_and_garlic',
          now: DateTime(2026, 1, 1),
        );

        final snapshot = await repository.getAll(userId);
        expect(snapshot, hasLength(1));
        expect(snapshot.single.canonicalName, 'garlic');
      });
    });

    group('addItems (review-screen commit)', () {
      test('commits every item in one transaction', () async {
        final ids = await repository.addItems(
          userId: userId,
          items: const [
            PantryItemInput(
              name: 'onion',
              quantity: 3,
              unit: 'unit',
              groupId: 'onions_and_garlic',
            ),
            PantryItemInput(
              name: 'lemon',
              quantity: 2,
              unit: 'unit',
              groupId: 'fruit',
            ),
          ],
          now: DateTime(2026, 1, 1),
        );

        expect(ids, hasLength(2));
        expect(await repository.watchAll(userId).first, hasLength(2));
      });

      test(
        'a failure partway through persists nothing, so retrying cannot double quantities',
        () async {
          final badBatch = [
            const PantryItemInput(
              name: 'onion',
              quantity: 3,
              unit: 'unit',
              groupId: 'onions_and_garlic',
            ),
            const PantryItemInput(
              name: 'mystery item',
              quantity: 1,
              unit: 'unit',
              groupId: 'not_a_real_category', // rejected by the group FK
            ),
          ];

          await expectLater(
            repository.addItems(
              userId: userId,
              items: badBatch,
              now: DateTime(2026, 1, 1),
            ),
            throwsA(anything),
          );
          // The first row's insert must have rolled back with the rest —
          // nothing partially committed (unlike RN's un-transacted loop).
          expect(await repository.watchAll(userId).first, isEmpty);

          // Retrying with an all-valid batch (as the review screen would,
          // after the user fixes the bad row) must not double the earlier
          // attempt's quantity, because nothing from it was ever persisted.
          final goodBatch = [
            const PantryItemInput(
              name: 'onion',
              quantity: 3,
              unit: 'unit',
              groupId: 'onions_and_garlic',
            ),
          ];
          await repository.addItems(
            userId: userId,
            items: goodBatch,
            now: DateTime(2026, 1, 1),
          );

          final items = await repository.watchAll(userId).first;
          expect(items, hasLength(1));
          expect(items.single.quantity, 3);
        },
      );
    });

    test(
      'undoing a recorded batch of additions removes the Pantry items it created and '
      'returns merged stock to its previous quantity',
      () async {
        await repository.addItem(
          userId: userId,
          name: 'milk',
          quantity: 1,
          unit: 'l',
          groupId: 'dairy',
          now: DateTime(2026, 1, 1),
        );

        final receipt = await repository.addItemsWithReceipt(
          userId: userId,
          items: const <PantryItemInput>[
            PantryItemInput(
              name: 'milk',
              quantity: 2,
              unit: 'l',
              groupId: 'dairy',
            ),
            PantryItemInput(
              name: 'eggs',
              quantity: 6,
              unit: 'units',
              groupId: 'dairy',
            ),
          ],
          now: DateTime(2026, 1, 2),
        );
        final afterAdd = await repository.watchAll(userId).first;
        expect(
          {for (final i in afterAdd) i.canonicalName: i.quantity},
          {'milk': 3000.0, 'eggs': 6.0},
        );

        await repository.undoAdditions(userId: userId, receipt: receipt);

        final afterUndo = await repository.watchAll(userId).first;
        expect(
          {for (final i in afterUndo) i.canonicalName: i.quantity},
          {'milk': 1000.0},
        );
      },
    );

    test(
      'a Pantry item added without an ingredient group is stored unclassified, in the '
      '"other" food group, with no inferred expiry',
      () async {
        await repository.addItems(
          userId: userId,
          items: const <PantryItemInput>[
            PantryItemInput(
              name: 'mystery sauce',
              quantity: 1,
              unit: 'jar',
              groupId: null,
            ),
          ],
          now: DateTime(2026, 1, 1),
        );

        final item = (await repository.watchAll(userId).first).single;
        expect(item.groupId, isNull);
        expect(item.foodGroup, 'other');
        expect(item.expiryDate, isNull);
      },
    );
  });
}
