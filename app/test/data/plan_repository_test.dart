// Real-outcome tests for the Plan repository: week scoping and pagination,
// per-week rather than lifetime capacity, idempotent rollover, honoured
// `servings`, and undoable "Cooked".
import 'package:glean/data/database.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('PlanRepository', () {
    late GleanDatabase db;
    late PlanRepository repository;
    late PantryRepository pantryRepository;
    late RecipesRepository recipesRepository;
    late UserConfigRepository userConfigRepository;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      final ingredients = IngredientsRepository(db);
      pantryRepository = PantryRepository(db, ingredients);
      recipesRepository = RecipesRepository(db, ingredients);
      userConfigRepository = UserConfigRepository(db);
      repository = PlanRepository(db, pantryRepository);
    });

    tearDown(() => db.close());

    Future<int> createRecipe(
      String title, {
      List<SaveRecipeIngredient> ingredients = const [],
    }) {
      return recipesRepository.save(
        userId: userId,
        title: title,
        ingredients: ingredients,
      );
    }

    Future<void> setMealsPerWeek(int mealsPerWeek) {
      return userConfigRepository.save(
        UserConfigView(
          id: userId,
          purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
          preferredServings: UserConfigView.defaultPreferredServings,
          mealsPerWeek: mealsPerWeek,
          dietaryFlags: const [],
          maxActiveTimeMins: null,
        ),
      );
    }

    test('watchWeek only returns entries within the given week', () async {
      final week1 = startOfWeek(DateTime(2026, 1, 5));
      final week2 = startOfWeek(DateTime(2026, 1, 12));
      final recipe1 = await createRecipe('Week 1 meal');
      final recipe2 = await createRecipe('Week 2 meal');

      await repository.addEntry(
        userId: userId,
        recipeId: recipe1,
        recipeTitle: 'Week 1 meal',
        servings: 2,
        plannedDate: week1,
      );
      await repository.addEntry(
        userId: userId,
        recipeId: recipe2,
        recipeTitle: 'Week 2 meal',
        servings: 2,
        plannedDate: week2,
      );

      final week1Entries = await repository
          .watchWeek(userId: userId, weekStart: week1)
          .first;
      expect(week1Entries.map((e) => e.recipeTitle), ['Week 1 meal']);

      // Pagination: last week's entries remain reachable by paging back
      // rather than disappearing.
      final week2Entries = await repository
          .watchWeek(userId: userId, weekStart: week2)
          .first;
      expect(week2Entries.map((e) => e.recipeTitle), ['Week 2 meal']);
    });

    test('addEntry honours the given servings — never hardcodes 1', () async {
      final week = startOfWeek(DateTime(2026, 1, 5));
      final recipeId = await createRecipe('Big batch');
      await repository.addEntry(
        userId: userId,
        recipeId: recipeId,
        recipeTitle: 'Big batch',
        servings: 6,
        plannedDate: week,
      );

      final entries = await repository
          .watchWeek(userId: userId, weekStart: week)
          .first;
      expect(entries.single.servings, 6);
    });

    test('getWeek is a one-shot snapshot scoped like watchWeek', () async {
      final week1 = startOfWeek(DateTime(2026, 1, 5));
      final week2 = startOfWeek(DateTime(2026, 1, 12));
      final recipe1 = await createRecipe('Week 1 meal');
      final recipe2 = await createRecipe('Week 2 meal');

      await repository.addEntry(
        userId: userId,
        recipeId: recipe1,
        recipeTitle: 'Week 1 meal',
        servings: 2,
        plannedDate: week1,
      );
      await repository.addEntry(
        userId: userId,
        recipeId: recipe2,
        recipeTitle: 'Week 2 meal',
        servings: 2,
        plannedDate: week2,
      );

      final week1Snapshot = await repository.getWeek(
        userId: userId,
        weekStart: week1,
      );
      expect(week1Snapshot.map((e) => e.recipeTitle), ['Week 1 meal']);

      final week2Snapshot = await repository.getWeek(
        userId: userId,
        weekStart: week2,
      );
      expect(week2Snapshot.map((e) => e.recipeTitle), ['Week 2 meal']);
    });

    group('capacity', () {
      test('is per-week, not lifetime', () async {
        await setMealsPerWeek(2);
        final week1 = startOfWeek(DateTime(2026, 1, 5));
        final week2 = startOfWeek(DateTime(2026, 1, 12));
        final recipeA = await createRecipe('A');
        final recipeB = await createRecipe('B');

        // Fill week 1 to capacity.
        await repository.addEntry(
          userId: userId,
          recipeId: recipeA,
          recipeTitle: 'A',
          servings: 1,
          plannedDate: week1,
        );
        await repository.addEntry(
          userId: userId,
          recipeId: recipeB,
          recipeTitle: 'B',
          servings: 1,
          plannedDate: week1,
        );

        expect(
          await repository.remainingCapacityForWeek(
            userId: userId,
            weekStart: week1,
          ),
          0,
        );
        // A week that was full a while ago has no bearing on this week —
        // unlike RN's lifetime count, which locked out every future add.
        expect(
          await repository.remainingCapacityForWeek(
            userId: userId,
            weekStart: week2,
          ),
          2,
        );
      });

      test('cooked meals free up their slot', () async {
        await setMealsPerWeek(2);
        final week = startOfWeek(DateTime(2026, 1, 5));
        final recipeA = await createRecipe('A');
        final recipeB = await createRecipe('B');
        final entryId = await repository.addEntry(
          userId: userId,
          recipeId: recipeA,
          recipeTitle: 'A',
          servings: 1,
          plannedDate: week,
        );
        await repository.addEntry(
          userId: userId,
          recipeId: recipeB,
          recipeTitle: 'B',
          servings: 1,
          plannedDate: week,
        );
        expect(
          await repository.remainingCapacityForWeek(
            userId: userId,
            weekStart: week,
          ),
          0,
        );

        await repository.markCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2026, 1, 6),
        );

        final entries = await repository
            .watchWeek(userId: userId, weekStart: week)
            .first;
        expect(entries, hasLength(2)); // cooked entry stays visible
        expect(
          await repository.remainingCapacityForWeek(
            userId: userId,
            weekStart: week,
          ),
          1,
        );
      });
    });

    group('cookedSince', () {
      test(
        'returns cooked entries in the window newest first, whatever ISO form they were stored in',
        () async {
          final week = startOfWeek(DateTime(2026, 1, 5));
          final recent = await createRecipe('Recent');
          final older = await createRecipe('Older');
          final stale = await createRecipe('Stale');
          final uncooked = await createRecipe('Uncooked');
          Future<int> planned(int recipeId, String title) =>
              repository.addEntry(
                userId: userId,
                recipeId: recipeId,
                recipeTitle: title,
                servings: 1,
                plannedDate: week,
              );
          final recentId = await planned(recent, 'Recent');
          final olderId = await planned(older, 'Older');
          final staleId = await planned(stale, 'Stale');
          await planned(uncooked, 'Uncooked');
          await repository.markCooked(
            entryId: recentId,
            userId: userId,
            now: DateTime(2026, 2, 20, 18),
          );
          await repository.markCooked(
            entryId: olderId,
            userId: userId,
            now: DateTime(2026, 1, 20, 18),
          );
          await repository.markCooked(
            entryId: staleId,
            userId: userId,
            now: DateTime(2025, 11, 1, 18),
          );
          // A backup restore can bring a UTC-stamped row in beside the app's local ones.
          await db.customStatement(
            "UPDATE meal_plan_entries SET cooked_at = '2026-02-10T18:00:00.000Z' WHERE id = ?",
            [olderId],
          );

          final cookedOut = await repository.cookedSince(
            userId: userId,
            since: DateTime(2026, 1, 5),
          );

          expect(cookedOut.map((entry) => entry.recipeTitle), [
            'Recent',
            'Older',
          ]);
        },
      );
    });

    group('rollover', () {
      test('moves uncooked entries into the current week', () async {
        final oldWeek = startOfWeek(DateTime(2025, 12, 1));
        final currentWeek = startOfWeek(DateTime(2026, 1, 5));
        final recipeId = await createRecipe('Carried over');

        await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Carried over',
          servings: 1,
          plannedDate: oldWeek,
        );

        await repository.rolloverUncookedMeals(
          userId: userId,
          referenceDate: DateTime(2026, 1, 5),
        );

        expect(
          await repository.watchWeek(userId: userId, weekStart: oldWeek).first,
          isEmpty,
        );
        final rolled = await repository
            .watchWeek(userId: userId, weekStart: currentWeek)
            .first;
        expect(rolled, hasLength(1));
        expect(rolled.single.plannedDate, currentWeek);
      });

      test(
        'is idempotent — running it twice does not duplicate entries',
        () async {
          final oldWeek = startOfWeek(DateTime(2025, 12, 1));
          final currentWeek = startOfWeek(DateTime(2026, 1, 5));
          final recipeId = await createRecipe('Carried over');

          await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'Carried over',
            servings: 1,
            plannedDate: oldWeek,
          );

          await repository.rolloverUncookedMeals(
            userId: userId,
            referenceDate: DateTime(2026, 1, 5),
          );
          await repository.rolloverUncookedMeals(
            userId: userId,
            referenceDate: DateTime(2026, 1, 5),
          );

          final rolled = await repository
              .watchWeek(userId: userId, weekStart: currentWeek)
              .first;
          expect(rolled, hasLength(1));
        },
      );

      test('never moves a cooked entry', () async {
        final oldWeek = startOfWeek(DateTime(2025, 12, 1));
        final recipeId = await createRecipe('Already cooked');
        final entryId = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Already cooked',
          servings: 1,
          plannedDate: oldWeek,
        );
        await repository.markCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2025, 12, 2),
        );

        await repository.rolloverUncookedMeals(
          userId: userId,
          referenceDate: DateTime(2026, 1, 5),
        );

        final stillInOldWeek = await repository
            .watchWeek(userId: userId, weekStart: oldWeek)
            .first;
        expect(stillInOldWeek, hasLength(1));
      });
    });

    group('markCooked / undoCooked', () {
      Future<int> saveChickenRecipe() {
        return createRecipe(
          'Chicken dinner',
          ingredients: const [
            SaveRecipeIngredient(
              canonicalName: 'chicken breast',
              quantity: 200,
              unit: 'g',
            ),
          ],
        );
      }

      test(
        'decrements pantry quantities scaled by servings and stamps cookedAt',
        () async {
          await pantryRepository.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 500,
            unit: 'g',
            groupId: 'poultry',
            now: DateTime(2026, 1, 1),
          );
          final recipeId = await saveChickenRecipe();
          final entryId = await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'Chicken dinner',
            servings: 2, // 200g * 2 = 400g needed
            plannedDate: startOfWeek(DateTime(2026, 1, 5)),
          );

          await repository.markCooked(
            entryId: entryId,
            userId: userId,
            now: DateTime(2026, 1, 6),
          );

          final pantry = await pantryRepository.watchAll(userId).first;
          expect(pantry.single.quantity, 100); // 500 - 400

          final entries = await repository
              .watchWeek(
                userId: userId,
                weekStart: startOfWeek(DateTime(2026, 1, 5)),
              )
              .first;
          expect(entries.single.isCooked, isTrue);
        },
      );

      test('undoCooked restores the exact pantry quantity', () async {
        await pantryRepository.addItem(
          userId: userId,
          name: 'chicken breast',
          quantity: 500,
          unit: 'g',
          groupId: 'poultry',
          now: DateTime(2026, 1, 1),
        );
        final recipeId = await saveChickenRecipe();
        final entryId = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Chicken dinner',
          servings: 2,
          plannedDate: startOfWeek(DateTime(2026, 1, 5)),
        );
        await repository.markCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2026, 1, 6),
        );

        await repository.undoCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2026, 1, 7),
        );

        final pantry = await pantryRepository.watchAll(userId).first;
        expect(pantry.single.quantity, 500); // exactly restored

        final entries = await repository
            .watchWeek(
              userId: userId,
              weekStart: startOfWeek(DateTime(2026, 1, 5)),
            )
            .first;
        expect(entries.single.isCooked, isFalse);
      });

      test(
        'undoCooked restores exactly even when the decrement was floored at zero',
        () async {
          // Pantry only has 100g; the recipe wants 400g. The applied delta
          // (100g, not 400g) is what must come back — over-restoring would
          // invent stock that was never actually there.
          await pantryRepository.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 100,
            unit: 'g',
            groupId: 'poultry',
            now: DateTime(2026, 1, 1),
          );
          final recipeId = await saveChickenRecipe();
          final entryId = await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'Chicken dinner',
            servings: 2,
            plannedDate: startOfWeek(DateTime(2026, 1, 5)),
          );

          await repository.markCooked(
            entryId: entryId,
            userId: userId,
            now: DateTime(2026, 1, 6),
          );
          var pantry = await pantryRepository.watchAll(userId).first;
          expect(pantry.single.quantity, 0);

          await repository.undoCooked(
            entryId: entryId,
            userId: userId,
            now: DateTime(2026, 1, 7),
          );
          pantry = await pantryRepository.watchAll(userId).first;
          expect(pantry.single.quantity, 100);
        },
      );

      test(
        'throws when marking an already-cooked entry cooked again',
        () async {
          final recipeId = await createRecipe('No pantry impact');
          final entryId = await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'No pantry impact',
            servings: 1,
            plannedDate: startOfWeek(DateTime(2026, 1, 5)),
          );
          await repository.markCooked(
            entryId: entryId,
            userId: userId,
            now: DateTime(2026, 1, 6),
          );

          await expectLater(
            repository.markCooked(
              entryId: entryId,
              userId: userId,
              now: DateTime(2026, 1, 7),
            ),
            throwsStateError,
          );
        },
      );

      test('undoing an earlier cook does not clobber a later cook\'s '
          'lastUsedAt while the later cook is still standing', () async {
        await pantryRepository.addItem(
          userId: userId,
          name: 'chicken breast',
          quantity: 1000,
          unit: 'g',
          groupId: 'poultry',
          now: DateTime(2026, 1, 1),
        );
        final recipeId = await saveChickenRecipe();
        final week = startOfWeek(DateTime(2026, 1, 5));
        // Two separate plan entries for the same recipe/ingredient — e.g.
        // chicken dinner planned twice in the same week.
        final entryA = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Chicken dinner',
          servings: 1, // 200g
          plannedDate: week,
        );
        final entryB = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Chicken dinner',
          servings: 1, // 200g
          plannedDate: week,
        );

        await repository.markCooked(
          entryId: entryA,
          userId: userId,
          now: DateTime(2026, 1, 6),
        );
        await repository.markCooked(
          entryId: entryB,
          userId: userId,
          now: DateTime(2026, 1, 7),
        );
        var pantry = (await pantryRepository.watchAll(userId).first).single;
        expect(pantry.quantity, 600); // 1000 - 200 - 200
        expect(pantry.lastUsedAt, DateTime(2026, 1, 7)); // B's cook

        // Undo the earlier cook (A) while B is still cooked.
        await repository.undoCooked(
          entryId: entryA,
          userId: userId,
          now: DateTime(2026, 1, 8),
        );

        pantry = (await pantryRepository.watchAll(userId).first).single;
        expect(pantry.quantity, 800); // A's 200g restored: 600 + 200
        // Must remain B's timestamp — B is still cooked and is the most
        // recent real use of this ingredient. The pre-fix bug restored
        // A's `previousLastUsedAt` snapshot (null) here, discarding B's
        // still-standing cook.
        expect(pantry.lastUsedAt, DateTime(2026, 1, 7));

        final entries = await repository
            .watchWeek(userId: userId, weekStart: week)
            .first;
        expect(entries.firstWhere((e) => e.id == entryA).isCooked, isFalse);
        expect(entries.firstWhere((e) => e.id == entryB).isCooked, isTrue);
      });

      test(
        'undoing the later cook after the earlier one is already undone '
        'still restores lastUsedAt, since no live adjustment remains',
        () async {
          await pantryRepository.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 1000,
            unit: 'g',
            groupId: 'poultry',
            now: DateTime(2026, 1, 1),
          );
          final recipeId = await saveChickenRecipe();
          final week = startOfWeek(DateTime(2026, 1, 5));
          final entryA = await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'Chicken dinner',
            servings: 1,
            plannedDate: week,
          );
          final entryB = await repository.addEntry(
            userId: userId,
            recipeId: recipeId,
            recipeTitle: 'Chicken dinner',
            servings: 1,
            plannedDate: week,
          );

          await repository.markCooked(
            entryId: entryA,
            userId: userId,
            now: DateTime(2026, 1, 6),
          );
          await repository.markCooked(
            entryId: entryB,
            userId: userId,
            now: DateTime(2026, 1, 7),
          );
          await repository.undoCooked(
            entryId: entryA,
            userId: userId,
            now: DateTime(2026, 1, 8),
          );

          // Now undo B too. Undoing A forwarded its pre-cook snapshot into
          // B's adjustment, preserving the chain after A's row was deleted.
          await repository.undoCooked(
            entryId: entryB,
            userId: userId,
            now: DateTime(2026, 1, 9),
          );

          final pantry = (await pantryRepository.watchAll(userId).first).single;
          expect(pantry.quantity, 1000); // fully restored
          expect(pantry.lastUsedAt, isNull);
        },
      );
    });

    group('ratings', () {
      final week = startOfWeek(DateTime(2026, 1, 5));

      Future<int> cookedEntry({String title = 'Curry'}) async {
        final recipeId = await createRecipe(title);
        final entryId = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: title,
          servings: 2,
          plannedDate: week,
        );
        await repository.markCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2026, 1, 6, 18),
        );
        return entryId;
      }

      Future<int> ratingRows() async {
        final rows = await db.select(db.mealRatings).get();
        return rows.length;
      }

      Future<MealPlanEntryView> readEntry(int entryId) async {
        final entries = await repository.getWeek(
          userId: userId,
          weekStart: week,
        );
        return entries.singleWhere((entry) => entry.id == entryId);
      }

      test(
        'a cooked meal can be rated either way, and the read carries it',
        () async {
          final entryId = await cookedEntry();

          await repository.rate(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.up,
          );

          expect((await readEntry(entryId)).rating, MealThumb.up);
          await repository.rate(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.down,
          );
          expect((await readEntry(entryId)).rating, MealThumb.down);
          expect(await ratingRows(), 1, reason: 'one rating per entry');
        },
      );

      test('switching the thumb drops the note that described the old one, '
          'and keeping it leaves the note alone', () async {
        final entryId = await cookedEntry();
        await repository.rateWithNote(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.down,
          note: 'too sweet',
        );
        expect((await readEntry(entryId)).note, 'too sweet');

        await repository.rate(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.down,
        );
        expect((await readEntry(entryId)).note, 'too sweet');

        await repository.rate(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.up,
        );
        expect((await readEntry(entryId)).note, isNull);
        expect((await readEntry(entryId)).rating, MealThumb.up);
      });

      test('a note is trimmed, and an empty one clears it', () async {
        final entryId = await cookedEntry();
        await repository.rateWithNote(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.up,
          note: '  kids loved it  ',
        );
        expect((await readEntry(entryId)).note, 'kids loved it');

        await repository.rateWithNote(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.up,
          note: '   ',
        );
        expect((await readEntry(entryId)).note, isNull);
      });

      test(
        'a note longer than the wire bound is refused, and nothing is written',
        () async {
          final entryId = await cookedEntry();
          final String tooLong =
              'e\u0301' * 300; // 600 code points for 300 visible characters

          await expectLater(
            repository.rateWithNote(
              entryId: entryId,
              userId: userId,
              rating: MealThumb.down,
              note: tooLong,
            ),
            throwsArgumentError,
          );

          expect(await ratingRows(), 0);
          expect((await readEntry(entryId)).rating, isNull);
        },
      );

      test(
        'clearing the thumb deletes the row, so the recipe is not avoided',
        () async {
          final entryId = await cookedEntry();
          await repository.rate(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.down,
          );

          await repository.clearRating(entryId: entryId, userId: userId);

          expect((await readEntry(entryId)).rating, isNull);
          expect(await ratingRows(), 0);
        },
      );

      test('an uncooked meal cannot be rated', () async {
        final recipeId = await createRecipe('Not yet');
        final entryId = await repository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Not yet',
          servings: 2,
          plannedDate: week,
        );

        await expectLater(
          repository.rate(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.up,
          ),
          throwsStateError,
        );
        expect(await ratingRows(), 0);
      });

      test('another user cannot rate this entry', () async {
        final entryId = await cookedEntry();

        await expectLater(
          repository.rate(
            entryId: entryId,
            userId: 'someone-else',
            rating: MealThumb.down,
          ),
          throwsStateError,
        );
        expect(await ratingRows(), 0);
      });

      test('undoing the cook clears the thumb too', () async {
        final entryId = await cookedEntry();
        await repository.rate(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.down,
        );

        await repository.undoCooked(
          entryId: entryId,
          userId: userId,
          now: DateTime(2026, 1, 7),
        );

        expect((await readEntry(entryId)).rating, isNull);
        expect(await ratingRows(), 0);
      });

      test(
        'deleting and undoing a rated meal restores the rating exactly',
        () async {
          final entryId = await cookedEntry();
          await repository.rateWithNote(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.down,
            note: 'too sweet',
          );

          final snapshot = await repository.deleteWithSnapshot(
            id: entryId,
            userId: userId,
          );
          expect(
            await ratingRows(),
            0,
            reason: 'the delete cascades the rating',
          );

          await repository.restoreDeleted(snapshot: snapshot, userId: userId);

          final restored = (await repository.getWeek(
            userId: userId,
            weekStart: week,
          )).single;
          expect(restored.id, entryId);
          expect(restored.rating, MealThumb.down);
          expect(restored.note, 'too sweet');
        },
      );

      test(
        'a thumbs down older than the window still travels, so it does not expire',
        () async {
          // One clock for the window and the ages in it: the helper cooks on 6 Jan, so the reference is the
          // day after, and the dislike is twenty weeks before that.
          final DateTime reference = DateTime(2026, 1, 7);
          final int old = await cookedEntry(title: 'Old dislike');
          await db.customStatement(
            'UPDATE meal_plan_entries SET cooked_at = ? WHERE id = ?',
            <Object?>[
              reference
                  .subtract(const Duration(days: 140))
                  .toUtc()
                  .toIso8601String(),
              old,
            ],
          );
          await repository.rateWithNote(
            entryId: old,
            userId: userId,
            rating: MealThumb.down,
            note: 'not again',
          );
          final int recent = await cookedEntry(title: 'Recent');
          await repository.rate(
            entryId: recent,
            userId: userId,
            rating: MealThumb.up,
          );

          final List<MealPlanEntryView> window = await repository.cookedHistory(
            userId: userId,
            now: reference,
          );
          expect(window.map((MealPlanEntryView entry) => entry.id), <int>[
            recent,
          ]);

          final List<MealPlanEntryView> history = await repository
              .plannerHistory(userId: userId, now: reference);
          expect(
            history.map((MealPlanEntryView entry) => entry.id).toSet(),
            <int>{old, recent},
          );
          final MealPlanEntryView sent = history.singleWhere(
            (MealPlanEntryView entry) => entry.id == old,
          );
          expect(sent.rating, MealThumb.down);
          expect(sent.note, 'not again');
          expect(
            sent.cookedAt!.isBefore(
              reference.subtract(const Duration(days: 100)),
            ),
            isTrue,
          );
        },
      );

      test(
        'a disliked cook inside the window is sent once, and clearing it removes '
        'the row',
        () async {
          final int entryId = await cookedEntry();
          await repository.rate(
            entryId: entryId,
            userId: userId,
            rating: MealThumb.down,
          );

          final List<MealPlanEntryView> inside = await repository
              .plannerHistory(userId: userId);
          expect(inside.map((MealPlanEntryView entry) => entry.id), <int>[
            entryId,
          ]);

          await repository.clearRating(entryId: entryId, userId: userId);
          expect(await repository.plannerHistory(userId: userId), isEmpty);
        },
      );

      test(
        'the latest disliked cook per recipe travels, and the list is bounded',
        () async {
          Future<int> agedDislike(String title, int daysAgo) async {
            final int entryId = await cookedEntry(title: title);
            await repository.rate(
              entryId: entryId,
              userId: userId,
              rating: MealThumb.down,
            );
            await db.customStatement(
              'UPDATE meal_plan_entries SET cooked_at = ? WHERE id = ?',
              <Object?>[
                DateTime.now()
                    .subtract(Duration(days: daysAgo))
                    .toUtc()
                    .toIso8601String(),
                entryId,
              ],
            );
            return entryId;
          }

          await agedDislike('Disliked twice', 300);
          final int second = await agedDislike('Disliked twice', 200);
          final int other = await agedDislike('Another dislike', 250);

          final List<MealPlanEntryView> all = await repository.plannerHistory(
            userId: userId,
          );
          expect(
            all.map((MealPlanEntryView entry) => entry.id).toSet(),
            <int>{second, other},
            reason: 'one row per recipe, its most recent rated cook',
          );

          final List<MealPlanEntryView> bounded = await repository
              .plannerHistory(userId: userId, dislikedLimit: 1);
          expect(bounded.map((MealPlanEntryView entry) => entry.id), <int>[
            second,
          ]);
        },
      );

      test('the history window carries each cook\'s rating and note', () async {
        final entryId = await cookedEntry();
        await repository.rateWithNote(
          entryId: entryId,
          userId: userId,
          rating: MealThumb.down,
          note: 'not again',
        );

        final history = await repository.cookedHistory(
          userId: userId,
          now: DateTime(2026, 1, 7),
        );

        expect(history.single.id, entryId);
        expect(history.single.rating, MealThumb.down);
        expect(history.single.note, 'not again');
      });
    });
  });
}
