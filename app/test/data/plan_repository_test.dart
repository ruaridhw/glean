// Real-outcome tests (AC-TEST-02) for the Plan schema changes
// FLUTTER_MIGRATION.md §6 Plan requires: week scoping and pagination
// (AC-PLAN-01/02), per-week rather than lifetime capacity (AC-PLAN-04),
// idempotent rollover (AC-PLAN-05, AC-TEST-09), honoured `servings`
// (AC-PLAN-07), and undoable "Cooked" (AC-UX-03, AC-TEST-08 data half).
import 'package:glean/data/database.dart';
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
      // (AC-PLAN-02) rather than disappearing.
      final week2Entries = await repository
          .watchWeek(userId: userId, weekStart: week2)
          .first;
      expect(week2Entries.map((e) => e.recipeTitle), ['Week 2 meal']);
    });

    test(
      'addEntry honours the given servings — never hardcodes 1 (AC-PLAN-07)',
      () async {
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
      },
    );

    test(
      'getWeek is a one-shot snapshot scoped like watchWeek (FINDINGS.md F-14)',
      () async {
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
      },
    );

    group('capacity', () {
      test('is per-week, not lifetime (AC-PLAN-04)', () async {
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

      test('cooked meals free up their slot (AC-PLAN-03/04)', () async {
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
        expect(
          entries,
          hasLength(2),
        ); // cooked entry stays visible (AC-PLAN-03)
        expect(
          await repository.remainingCapacityForWeek(
            userId: userId,
            weekStart: week,
          ),
          1,
        );
      });
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
            category: 'poultry',
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

      test(
        'undoCooked restores the exact pantry quantity (AC-UX-03, AC-TEST-08)',
        () async {
          await pantryRepository.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 500,
            unit: 'g',
            category: 'poultry',
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
        },
      );

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
            category: 'poultry',
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
    });
  });
}
