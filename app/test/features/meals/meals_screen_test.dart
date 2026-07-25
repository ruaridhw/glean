// Widget coverage for the Saved segment of the Meals tab: empty state,
// listing, and swipe-to-delete + undo — including AC-MEAL-03's requirement
// that a referencing plan entry survives a recipe delete with its
// `recipeTitle` snapshot intact.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';

import 'test_harness.dart';

void main() {
  group('MealsScreen — Saved segment', () {
    late MealsTestHarness harness;
    late RecipesRepository recipes;
    late PlanRepository plan;

    setUp(() {
      harness = MealsTestHarness();
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

      expect(find.text('No saved recipes'), findsOneWidget);
    });

    testWidgets('lists saved recipes and navigates to detail on tap', (
      WidgetTester tester,
    ) async {
      await recipes.save(
        userId: 'user-a',
        externalId: 'ext-1',
        title: 'Tomato Pasta',
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.meals.path);
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
      'swipe-to-delete removes a recipe with undo, keeping a referencing '
      'plan entry with its title snapshot intact (AC-MEAL-03)',
      (WidgetTester tester) async {
        final int recipeId = await recipes.save(
          userId: 'user-a',
          externalId: 'ext-2',
          title: 'Chicken Curry',
          ingredients: const <SaveRecipeIngredient>[],
        );
        final int entryId = await plan.addEntry(
          userId: 'user-a',
          recipeId: recipeId,
          recipeTitle: 'Chicken Curry',
          servings: 2,
        );

        await harness.pumpAt(tester, AppRoutes.meals.path);
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
          await tester.runAsync(() => recipes.watchSaved('user-a').first),
          isEmpty,
        );

        // The plan entry survives the delete, unlinked but with its title
        // snapshot untouched.
        final entryAfterDelete = (await tester.runAsync(
          () => plan
              .watchWeek(
                userId: 'user-a',
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
          await tester.runAsync(() => recipes.watchSaved('user-a').first),
          hasLength(1),
        );
        expect(find.text('Chicken Curry'), findsOneWidget);
      },
    );
  });
}
