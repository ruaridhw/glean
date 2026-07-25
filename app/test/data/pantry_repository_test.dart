// Real-outcome tests for pantry reads/writes (AC-TEST-02), covering the
// schema changes FLUTTER_MIGRATION.md §6 Pantry requires that the RN app
// never had: automatic expiry inference (AC-PAN-01, AC-TEST-10) and a
// guaranteed non-null `foodGroup` on every row (AC-DATA-11).
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
      'addItem infers an expiry date from the category shelf life',
      () async {
        final now = DateTime(2026, 1, 1);
        await repository.addItem(
          userId: userId,
          name: 'strawberries',
          quantity: 1,
          unit: 'punnet',
          category: 'berries', // 4-day shelf life
          now: now,
        );

        final items = await repository.watchAll(userId).first;
        expect(items, hasLength(1));
        expect(items.single.expiryDate, DateTime(2026, 1, 5));
      },
    );

    test(
      'the persisted category survives — food_group is never null',
      () async {
        await repository.addItem(
          userId: userId,
          name: 'aubergine',
          quantity: 2,
          unit: 'unit',
          category: 'nightshades',
          now: DateTime(2026, 1, 1),
        );

        final items = await repository.watchAll(userId).first;
        expect(items.single.category, 'nightshades');
        expect(items.single.foodGroup, 'vegetables');
      },
    );

    test(
      'a pantry item whose ingredient has no category still appears, with foodGroup "other" (regression)',
      () async {
        // Simulates an ingredient that reached the pantry with no
        // category at all — e.g. one first created by recipe import
        // (which has no category source, §9) and never since resolved
        // through a categorised pantry/shopping intake path. `addItem`
        // itself always supplies a category, so this bypasses it
        // deliberately, the same way a future insert path that forgets to
        // would.
        final ingredients = IngredientsRepository(db);
        final ingredient = await ingredients.resolveOrCreate(
          canonicalName: 'mystery meat',
        );
        expect(ingredient.category, isNull);
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
        expect(items.single.category, isNull);
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
          category: 'dairy',
          now: DateTime(2026, 1, 1),
        );
        await repository.addItem(
          userId: userId,
          name: 'milk',
          quantity: 500,
          unit: 'ml',
          category: 'dairy',
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
      '(R-18 — even the very first add, which is also what sets the target)',
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
          category: 'grains',
          now: DateTime(2026, 1, 1),
        );

        final items = await repository.watchAll(userId).first;
        expect(items.single.unit, 'g');
        expect(items.single.quantity, 1000);
      },
    );

    test('a mixed-unit top-up converts and sums correctly instead of '
        'corrupting the quantity (R-18 regression)', () async {
      // The exact scenario R-18 describes: "2 kg flour" then "500 g
      // flour" must total 2500g, never the RN/pre-fix bug's "502 kg".
      await repository.addItem(
        userId: userId,
        name: 'plain flour',
        quantity: 2,
        unit: 'kg',
        category: 'grains',
        now: DateTime(2026, 1, 1),
      );
      await repository.addItem(
        userId: userId,
        name: 'plain flour',
        quantity: 500,
        unit: 'g',
        category: 'grains',
        now: DateTime(2026, 1, 3),
      );

      final items = await repository.watchAll(userId).first;
      expect(items, hasLength(1));
      expect(items.single.unit, 'g');
      expect(items.single.quantity, 2500);
    });

    test('a genuinely incompatible unit merge throws rather than silently '
        'summing under the wrong unit (R-18)', () async {
      // First add establishes 'units' as garlic's canonical unit (not a
      // recognised mass/volume unit, so it becomes the literal unit).
      await repository.addItem(
        userId: userId,
        name: 'garlic',
        quantity: 3,
        unit: 'units',
        category: 'alliums',
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
          category: 'alliums',
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

    test('updateItem changes only the fields provided', () async {
      final now = DateTime(2026, 1, 1);
      await repository.addItem(
        userId: userId,
        name: 'butter',
        quantity: 250,
        unit: 'g',
        category: 'dairy',
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
        category: 'eggs',
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
            category: 'poultry',
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
            category: 'pasta_rice',
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
          ).resolveOrCreate(canonicalName: 'saffron', category: 'spices');

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

    group('getAll (one-shot snapshot, FINDINGS.md F-14)', () {
      test('matches watchAll\'s rows for the same user', () async {
        await repository.addItem(
          userId: userId,
          name: 'strawberries',
          quantity: 1,
          unit: 'punnet',
          category: 'berries',
          now: DateTime(2026, 1, 1),
        );

        final snapshot = await repository.getAll(userId);
        expect(snapshot, hasLength(1));
        expect(snapshot.single.canonicalName, 'strawberries');
        expect(snapshot.single.foodGroup, 'fruit');
      });

      test(
        'a pantry item whose ingredient has no category still appears, '
        'with foodGroup "other" (regression, same join shape as watchAll)',
        () async {
          final ingredients = IngredientsRepository(db);
          final ingredient = await ingredients.resolveOrCreate(
            canonicalName: 'mystery meat',
          );
          expect(ingredient.category, isNull);
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
          // null category must never disappear the row (data-loss bug
          // already fixed once for the stream version).
          expect(snapshot, hasLength(1));
          expect(snapshot.single.canonicalName, 'mystery meat');
          expect(snapshot.single.category, isNull);
          expect(snapshot.single.foodGroup, 'other');
          expect(snapshot.single.shelfLifeDays, isNull);
        },
      );

      test('only returns the given user\'s items (AC-DATA-02/03)', () async {
        await repository.addItem(
          userId: userId,
          name: 'garlic',
          quantity: 1,
          unit: 'unit',
          category: 'alliums',
          now: DateTime(2026, 1, 1),
        );
        await repository.addItem(
          userId: 'user-b',
          name: 'ginger',
          quantity: 1,
          unit: 'unit',
          category: 'alliums',
          now: DateTime(2026, 1, 1),
        );

        final snapshot = await repository.getAll(userId);
        expect(snapshot, hasLength(1));
        expect(snapshot.single.canonicalName, 'garlic');
      });
    });

    group('addItems (review-screen commit, AC-PAN-10)', () {
      test('commits every item in one transaction', () async {
        final ids = await repository.addItems(
          userId: userId,
          items: const [
            PantryItemInput(
              name: 'onion',
              quantity: 3,
              unit: 'unit',
              category: 'alliums',
            ),
            PantryItemInput(
              name: 'lemon',
              quantity: 2,
              unit: 'unit',
              category: 'citrus',
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
              category: 'alliums',
            ),
            const PantryItemInput(
              name: 'mystery item',
              quantity: 1,
              unit: 'unit',
              category: 'not_a_real_category', // rejected by the taxonomy FK
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
              category: 'alliums',
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
  });
}
