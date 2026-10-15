// Widget coverage for the Saved segment of the Meals tab: empty state,
// listing, swipe-to-delete + undo — including AC-MEAL-03's requirement
// that a referencing plan entry survives a recipe delete with its
// `recipeTitle` snapshot intact — and R-07's delete-failure guard.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';

import '../../data/fixture.dart';
import '../../support/harness.dart';

/// Forces `RecipesRepository.deleteRecipe` to fail, so R-07's guard around
/// `deleteRecipeWithUndo` can be exercised without a real DB failure mode to
/// hand — stays trivial (override the one method under test) since its only
/// job is injecting that one specific failure.
class _ThrowingDeleteRecipesRepository extends RecipesRepository {
  _ThrowingDeleteRecipesRepository(super.db, super.ingredients);

  @override
  Future<void> deleteRecipe({required int id, required String userId}) {
    return Future<void>.error(Exception('simulated DB failure'));
  }
}

void main() {
  group('MealsScreen — Saved segment', () {
    late AppTestHarness harness;
    late RecipesRepository recipes;
    late PlanRepository plan;

    setUp(() {
      harness = AppTestHarness();
      final ingredients = IngredientsRepository(harness.db);
      recipes = RecipesRepository(harness.db, ingredients);
      plan = PlanRepository(
        harness.db,
        PantryRepository(harness.db, ingredients),
      );
    });

    tearDown(() => harness.dispose());

    testWidgets('shows the empty state with no saved recipes', (
      WidgetTester tester,
    ) async {
      await harness.pumpAt(tester, AppRoutes.meals.path);
      // `pumpAt` deliberately does a single `pump()` — settle the
      // skeleton→content crossfade and the provider chain resolving.
      await tester.pumpAndSettle();

      expect(find.text('No saved recipes'), findsOneWidget);
    });

    testWidgets('lists saved recipes and navigates to detail on tap', (
      WidgetTester tester,
    ) async {
      await recipes.save(
        userId: 'test-user',
        externalId: 'ext-1',
        title: 'Tomato Pasta',
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.meals.path);
      // `pumpAt` deliberately does a single `pump()` — settle the
      // skeleton→content crossfade and the provider chain resolving.
      await tester.pumpAndSettle();
      expect(find.text('Tomato Pasta'), findsOneWidget);

      await tester.tap(find.text('Tomato Pasta'));
      await tester.pumpAndSettle();

      // The detail app bar shows the dish name (AC-MEAL-06), not a static
      // "Recipe" — there are now two matches (the app bar title and the
      // hero card is gone since it's folded into the app bar), so assert
      // via the AppBar specifically.
      expect(
        find.descendant(
          of: find.byType(AppBar),
          matching: find.text('Tomato Pasta'),
        ),
        findsOneWidget,
      );
    });

    testWidgets(
      'a saved recipe settles in via GleanListEntrance rather than popping '
      'in (R-10, AC-TRN-02)',
      (WidgetTester tester) async {
        await recipes.save(
          userId: 'test-user',
          externalId: 'ext-entrance',
          title: 'Lentil Soup',
          ingredients: const <SaveRecipeIngredient>[],
        );

        await harness.pumpAt(tester, AppRoutes.meals.path);
        await tester.pumpAndSettle();

        expect(
          find.ancestor(
            of: find.text('Lentil Soup'),
            matching: find.byType(GleanListEntrance),
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'swipe-to-delete removes a recipe with undo, keeping a referencing '
      'plan entry with its title snapshot intact (AC-MEAL-03)',
      (WidgetTester tester) async {
        final int recipeId = await recipes.save(
          userId: 'test-user',
          externalId: 'ext-2',
          title: 'Chicken Curry',
          ingredients: const <SaveRecipeIngredient>[],
        );
        final int entryId = await plan.addEntry(
          userId: 'test-user',
          recipeId: recipeId,
          recipeTitle: 'Chicken Curry',
          servings: 2,
        );

        await harness.pumpAt(tester, AppRoutes.meals.path);
        // `pumpAt` deliberately does a single `pump()` — settle the
        // skeleton→content crossfade and the provider chain resolving.
        await tester.pumpAndSettle();
        expect(find.text('Chicken Curry'), findsOneWidget);

        await tester.drag(find.text('Chicken Curry'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        expect(find.text('Chicken Curry removed'), findsOneWidget);
        expect(find.text('Undo'), findsOneWidget);
        // Raw repository stream queries made directly in a widget test (as
        // opposed to through the widget tree's own long-lived subscription)
        // must go through `tester.runAsync` — drift's `StreamQueryStore`
        // defers cleanup of a cancelled `.watch()` subscription via a real
        // `Timer.run()`, which the fake-clock zone `testWidgets` normally
        // runs in cannot service, hanging the test.
        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          isEmpty,
        );

        // The plan entry survives the delete, unlinked but with its title
        // snapshot untouched.
        final entryAfterDelete = (await tester.runAsync(
          () => plan
              .watchWeek(
                userId: 'test-user',
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        ))!.singleWhere((e) => e.id == entryId);
        expect(entryAfterDelete.recipeId, isNull);
        expect(entryAfterDelete.recipeTitle, 'Chicken Curry');

        await tester.tap(find.text('Undo'));
        await tester.pumpAndSettle();

        // Undo re-saves it (a new row — SQLite has no "undelete at the same
        // id"), so the library shows it again.
        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          hasLength(1),
        );
        expect(find.text('Chicken Curry'), findsOneWidget);
      },
    );

    gleanWidgetTest(
      'a delete failure is caught and surfaced, leaving the row intact '
      '(R-07)',
      (WidgetTester tester) async {
        final throwingDb = createTestDatabase();
        addTearDown(() => throwingDb.close());
        final throwingRepo = _ThrowingDeleteRecipesRepository(
          throwingDb,
          IngredientsRepository(throwingDb),
        );
        await throwingRepo.save(
          userId: 'test-user',
          title: 'Chicken Curry',
          ingredients: const <SaveRecipeIngredient>[],
        );

        final localHarness = AppTestHarness(
          overrides: [
            recipesRepositoryProvider.overrideWithValue(throwingRepo),
          ],
        );
        addTearDown(() => localHarness.dispose());

        await localHarness.pumpAt(tester, AppRoutes.meals.path);
        await tester.pumpAndSettle();
        expect(find.text('Chicken Curry'), findsOneWidget);

        await tester.drag(find.text('Chicken Curry'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        // No undo snackbar — the delete failed and was caught, not
        // propagated uncaught with zero feedback (the R-07 bug).
        expect(find.text('Undo'), findsNothing);
        expect(find.textContaining('Could not remove'), findsOneWidget);

        // The row must survive untouched in the data layer.
        final survivors = await tester.runAsync(
          () => throwingRepo.watchSaved('test-user').first,
        );
        expect(survivors!.single.title, 'Chicken Curry');
      },
    );
  });
}
