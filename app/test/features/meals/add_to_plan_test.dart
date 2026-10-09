// Widget coverage for "Add to plan" (AC-MEAL-08/09, AC-PLAN-11's Meals
// half): stays on the recipe, reflects "In plan" on the button, reports
// plan-full/already-planned *before* any mutation, and repeated
// rebuilds/refocus never add the recipe twice.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('SavedRecipeDetail — Add to plan', () {
    late AppTestHarness harness;
    late RecipesRepository recipes;
    late PlanRepository plan;
    late UserConfigRepository userConfig;

    setUp(() {
      harness = AppTestHarness();
      final ingredients = IngredientsRepository(harness.db);
      recipes = RecipesRepository(harness.db, ingredients);
      plan = PlanRepository(
        harness.db,
        PantryRepository(harness.db, ingredients),
      );
      userConfig = UserConfigRepository(harness.db);
    });

    tearDown(() => harness.dispose());

    testWidgets('stays on the recipe, shows a snackbar and flips the button to '
        '"In plan"', (WidgetTester tester) async {
      final int id = await recipes.save(
        userId: 'test-user',
        externalId: 'ext-1',
        title: 'Veggie Chilli',
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(FilledButton, 'Add to plan'), findsOneWidget);

      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();

      expect(find.text('Added to plan'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'In plan'), findsOneWidget);
      // Never navigated away — still on this recipe's own detail screen.
      expect(
        find.descendant(
          of: find.byType(AppBar),
          matching: find.text('Veggie Chilli'),
        ),
        findsOneWidget,
      );

      // A raw repository stream query in a widget test must go through
      // `tester.runAsync` — see `meals_screen_test.dart`'s comment.
      final entries = await tester.runAsync(
        () => plan
            .watchWeek(
              userId: 'test-user',
              weekStart: startOfWeek(DateTime.now()),
            )
            .first,
      );
      expect(entries, hasLength(1));
      expect(entries!.single.recipeId, id);
    });

    testWidgets('tapping "In plan" again reports it without adding a duplicate '
        '(AC-PLAN-11 Meals half)', (WidgetTester tester) async {
      final int id = await recipes.save(
        userId: 'test-user',
        externalId: 'ext-2',
        title: 'Baked Salmon',
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(FilledButton, 'In plan'), findsOneWidget);

      // Simulate leaving and returning to the same screen — the RN bug
      // this replaces (F-05) re-added on every focus; here there is no
      // focus effect to re-trigger at all, but assert the outcome anyway.
      await harness.pumpAt(tester, AppRoutes.meals.path);
      await tester.pumpAndSettle();
      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'In plan'));
      await tester.pumpAndSettle();

      expect(find.text('Already in your plan for this week.'), findsOneWidget);
      final entries = await tester.runAsync(
        () => plan
            .watchWeek(
              userId: 'test-user',
              weekStart: startOfWeek(DateTime.now()),
            )
            .first,
      );
      expect(entries, hasLength(1));
    });

    testWidgets(
      'plan-full is reported before any mutation is attempted (AC-MEAL-09)',
      (WidgetTester tester) async {
        await userConfig.save(
          const UserConfigView(
            id: 'test-user',
            purchaseTolerance: 0.5,
            preferredServings: 2,
            mealsPerWeek: 0,
            dietaryFlags: <String>[],
            maxActiveTimeMins: null,
          ),
        );
        final int id = await recipes.save(
          userId: 'test-user',
          externalId: 'ext-3',
          title: 'Full Week Meal',
          ingredients: const <SaveRecipeIngredient>[],
        );

        await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
        await tester.pumpAndSettle();

        expect(find.text("This week's plan is full."), findsOneWidget);
        expect(
          await tester.runAsync(
            () => plan
                .watchWeek(
                  userId: 'test-user',
                  weekStart: startOfWeek(DateTime.now()),
                )
                .first,
          ),
          isEmpty,
        );
        // The button never flips, since nothing was added.
        expect(
          find.widgetWithText(FilledButton, 'Add to plan'),
          findsOneWidget,
        );
      },
    );
  });
}
