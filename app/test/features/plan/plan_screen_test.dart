// Widget coverage for the Plan screen: week scoping and pagination
// (AC-PLAN-01/02), cooked meals visible-but-not-counted (AC-PLAN-03),
// per-week capacity (AC-PLAN-04), rollover on load (AC-PLAN-05), Generate
// disabled while pending (AC-PLAN-09), no re-add-on-focus (AC-PLAN-11),
// swipe-delete-with-undo cascading its shopping row (AC-UX-02/AC-SHOP-06),
// and cooked/undo restoring pantry exactly (AC-UX-03).
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/meals/meals_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../data/fixture.dart';
import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

/// Forces `PlanRepository.deleteEntry` to fail, so R-07's guard around
/// `deleteEntryWithUndo` can be exercised without a real DB failure mode to
/// hand — mirrors `_ThrowingDeletePantryRepository` in
/// `test/features/pantry/pantry_screen_test.dart`.
class _ThrowingDeletePlanRepository extends PlanRepository {
  _ThrowingDeletePlanRepository(super.db, super.pantry);

  @override
  Future<void> deleteEntry({required int id, required String userId}) {
    return Future<void>.error(Exception('simulated DB failure'));
  }
}

class _ThrowingMarkCookedPlanRepository extends PlanRepository {
  _ThrowingMarkCookedPlanRepository(super.db, super.pantry);

  @override
  Future<void> markCooked({
    required int entryId,
    required String userId,
    DateTime? now,
  }) {
    return Future<void>.error(Exception('simulated DB failure'));
  }
}

class _ThrowingUndoCookedPlanRepository extends PlanRepository {
  _ThrowingUndoCookedPlanRepository(super.db, super.pantry);

  @override
  Future<void> undoCooked({
    required int entryId,
    required String userId,
    DateTime? now,
  }) {
    return Future<void>.error(Exception('simulated DB failure'));
  }
}

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:9999/'));
  });

  group('PlanScreen', () {
    late AppTestHarness harness;
    late RecipesRepository recipes;
    late PlanRepository plan;
    late PantryRepository pantry;
    late ShoppingRepository shopping;
    late UserConfigRepository userConfig;

    setUp(() {
      harness = AppTestHarness();
      final ingredients = IngredientsRepository(harness.db);
      recipes = RecipesRepository(harness.db, ingredients);
      pantry = PantryRepository(harness.db, ingredients);
      plan = PlanRepository(harness.db, pantry);
      shopping = ShoppingRepository(harness.db, ingredients);
      userConfig = UserConfigRepository(harness.db);
    });

    tearDown(() => harness.dispose());

    Future<int> saveRecipe(
      String title, {
      List<SaveRecipeIngredient> ingredients = const <SaveRecipeIngredient>[],
    }) {
      return recipes.save(
        userId: harness.userId,
        title: title,
        ingredients: ingredients,
      );
    }

    Future<void> setMealsPerWeek(int n) {
      return userConfig.save(
        UserConfigView(
          id: harness.userId,
          purchaseTolerance: 0.5,
          preferredServings: 2,
          mealsPerWeek: n,
          dietaryFlags: const <String>[],
          maxActiveTimeMins: null,
        ),
      );
    }

    gleanWidgetTest(
      'shows only this week\'s entries; last week\'s cooked meal is '
      'reachable by paging back (AC-PLAN-01/02)',
      (WidgetTester tester) async {
        final lastWeek = startOfWeek(
          DateTime.now(),
        ).subtract(const Duration(days: 7));
        final oldId = await saveRecipe('Old Roast');
        final oldEntryId = await plan.addEntry(
          userId: harness.userId,
          recipeId: oldId,
          recipeTitle: 'Old Roast',
          servings: 2,
          plannedDate: lastWeek,
        );
        // Cooked, so the screen's own rollover (AC-PLAN-05 — uncooked only)
        // leaves it in last week rather than rolling it forward, which is
        // what this test needs to isolate week-scoping/pagination from
        // rollover.
        await plan.markCooked(
          entryId: oldEntryId,
          userId: harness.userId,
          now: lastWeek.add(const Duration(days: 1)),
        );
        final newId = await saveRecipe('Fresh Salad');
        await plan.addEntry(
          userId: harness.userId,
          recipeId: newId,
          recipeTitle: 'Fresh Salad',
          servings: 2,
        );

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();

        expect(find.text('Fresh Salad'), findsOneWidget);
        expect(find.text('Old Roast'), findsNothing);

        await tester.tap(find.byTooltip('Previous week'));
        await tester.pumpAndSettle();

        expect(find.text('Old Roast'), findsOneWidget);
        expect(find.text('Fresh Salad'), findsNothing);
      },
    );

    gleanWidgetTest(
      'cooked meals stay visible but stop counting toward "left to plan" '
      '(AC-PLAN-03)',
      (WidgetTester tester) async {
        await setMealsPerWeek(2);
        final cookedId = await saveRecipe('Cooked Dish');
        final pendingId = await saveRecipe('Pending Dish');
        final entryId = await plan.addEntry(
          userId: harness.userId,
          recipeId: cookedId,
          recipeTitle: 'Cooked Dish',
          servings: 2,
        );
        await plan.addEntry(
          userId: harness.userId,
          recipeId: pendingId,
          recipeTitle: 'Pending Dish',
          servings: 2,
        );
        await plan.markCooked(entryId: entryId, userId: harness.userId);

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();

        expect(find.text('Cooked Dish'), findsOneWidget);
        expect(find.text('Pending Dish'), findsOneWidget);
        expect(find.textContaining('· Cooked'), findsOneWidget);
        // Target 2, one cooked + one uncooked: only the uncooked one still
        // counts, so 1 remains — not 0, which `target - totalEntries` would
        // have wrongly given once cooked meals stopped counting.
        expect(find.text('1 dinner left to plan this week'), findsOneWidget);
        expect(find.text('2/2'), findsOneWidget); // satisfaction loop intact
      },
    );

    gleanWidgetTest(
      'capacity is per-week, not lifetime — a full week does not block '
      'the next (AC-PLAN-04)',
      (WidgetTester tester) async {
        await setMealsPerWeek(1);
        final id = await saveRecipe('This Week Only');
        await plan.addEntry(
          userId: harness.userId,
          recipeId: id,
          recipeTitle: 'This Week Only',
          servings: 2,
        );

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();

        expect(find.text('Add a dinner'), findsNothing);
        expect(find.text('Week fully planned — nice'), findsOneWidget);

        await tester.tap(find.byTooltip('Next week'));
        await tester.pumpAndSettle();

        expect(find.text('Add a dinner'), findsOneWidget);
        expect(find.text('1 dinner left to plan this week'), findsOneWidget);
      },
    );

    gleanWidgetTest(
      'rollover moves an uncooked meal from an earlier week into this week '
      'on load, idempotently (AC-PLAN-05)',
      (WidgetTester tester) async {
        final earlierWeek = startOfWeek(
          DateTime.now(),
        ).subtract(const Duration(days: 14));
        final id = await saveRecipe('Carried Over');
        await plan.addEntry(
          userId: harness.userId,
          recipeId: id,
          recipeTitle: 'Carried Over',
          servings: 2,
          plannedDate: earlierWeek,
        );

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();

        expect(find.text('Carried Over'), findsOneWidget);

        // A repeat rollover (as the screen's own `initState` fires on every
        // mount) must not duplicate the entry.
        await plan.rolloverUncookedMeals(
          userId: harness.userId,
          referenceDate: DateTime.now(),
        );
        final entries = await tester.runAsync(
          () => plan
              .watchWeek(
                userId: harness.userId,
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        );
        expect(entries, hasLength(1));
      },
    );

    gleanWidgetTest(
      'navigating away from Plan and back adds nothing (AC-PLAN-11)',
      (WidgetTester tester) async {
        await tester.pumpWidget(harness.app());
        await tester.pumpAndSettle();

        Future<void> tapTab(String label) async {
          await tester.tap(
            find.descendant(
              of: find.byType(NavigationBar),
              matching: find.text(label),
            ),
          );
          await tester.pumpAndSettle();
        }

        await tapTab('Plan');
        var entries = await tester.runAsync(
          () => plan
              .watchWeek(
                userId: harness.userId,
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        );
        expect(entries, isEmpty);

        await tapTab('Meals');
        await tapTab('Plan');

        entries = await tester.runAsync(
          () => plan
              .watchWeek(
                userId: harness.userId,
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        );
        expect(entries, isEmpty);
      },
    );

    gleanWidgetTest(
      'tapping an empty "Add a dinner" slot fires a haptic and opens Meals '
      '(AC-HAP-05)',
      (WidgetTester tester) async {
        await setMealsPerWeek(1);
        await tester.pumpWidget(harness.app());
        await tester.pumpAndSettle();

        await tester.tap(
          find.descendant(
            of: find.byType(NavigationBar),
            matching: find.text('Plan'),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Add a dinner'), findsOneWidget);
        await tester.tap(find.text('Add a dinner'));
        await tester.pumpAndSettle();

        expect(find.byType(MealsScreen), findsOneWidget);
        expect(harness.hapticCalls, contains(HapticWeight.light));
      },
    );

    gleanWidgetTest(
      'swipe-to-delete removes the entry and cascades its shopping row, '
      'with undo restoring the entry (AC-UX-02, AC-SHOP-06)',
      (WidgetTester tester) async {
        final id = await saveRecipe(
          'Weeknight Curry',
          ingredients: const <SaveRecipeIngredient>[
            SaveRecipeIngredient(
              canonicalName: 'coconut milk',
              quantity: 400,
              unit: 'ml',
            ),
          ],
        );
        final entryId = await plan.addEntry(
          userId: harness.userId,
          recipeId: id,
          recipeTitle: 'Weeknight Curry',
          servings: 3,
        );
        await shopping.addGapsForRecipe(
          userId: harness.userId,
          recipeId: id,
          servings: 3,
          sourceMealPlanEntryId: entryId,
        );
        expect(
          await tester.runAsync(() => shopping.watchAll(harness.userId).first),
          hasLength(1),
        );

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();
        expect(find.text('Weeknight Curry'), findsOneWidget);

        await tester.drag(find.text('Weeknight Curry'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        expect(find.text('Weeknight Curry removed'), findsOneWidget);
        expect(
          await tester.runAsync(
            () => plan
                .watchWeek(
                  userId: harness.userId,
                  weekStart: startOfWeek(DateTime.now()),
                )
                .first,
          ),
          isEmpty,
        );
        expect(
          await tester.runAsync(() => shopping.watchAll(harness.userId).first),
          isEmpty,
        );

        await tester.tap(find.text('Undo'));
        await tester.pumpAndSettle();

        expect(find.text('Weeknight Curry'), findsOneWidget);
        final restored = await tester.runAsync(
          () => plan
              .watchWeek(
                userId: harness.userId,
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        );
        expect(restored, hasLength(1));
        expect(restored!.single.servings, 3);
      },
    );

    gleanWidgetTest(
      'a delete failure is caught and surfaced, leaving the entry intact '
      '(R-07)',
      (WidgetTester tester) async {
        final throwingDb = createTestDatabase();
        addTearDown(() => throwingDb.close());
        final throwingIngredients = IngredientsRepository(throwingDb);
        final throwingPantry = PantryRepository(
          throwingDb,
          throwingIngredients,
        );
        final throwingRepo = _ThrowingDeletePlanRepository(
          throwingDb,
          throwingPantry,
        );
        final throwingRecipes = RecipesRepository(
          throwingDb,
          throwingIngredients,
        );
        final id = await throwingRecipes.save(
          userId: 'test-user',
          title: 'Weeknight Curry',
          ingredients: const <SaveRecipeIngredient>[],
        );
        await throwingRepo.addEntry(
          userId: 'test-user',
          recipeId: id,
          recipeTitle: 'Weeknight Curry',
          servings: 2,
        );

        final localHarness = AppTestHarness(
          overrides: [planRepositoryProvider.overrideWithValue(throwingRepo)],
        );
        addTearDown(() => localHarness.dispose());

        await localHarness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();
        expect(find.text('Weeknight Curry'), findsOneWidget);

        await tester.drag(find.text('Weeknight Curry'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        // No undo snackbar — the delete failed and was caught, not
        // propagated uncaught with zero feedback (the R-07 bug).
        expect(find.text('Undo'), findsNothing);
        expect(find.textContaining('Could not remove'), findsOneWidget);

        // The entry must survive untouched in the data layer.
        final survivors = await tester.runAsync(
          () => throwingRepo
              .watchWeek(
                userId: 'test-user',
                weekStart: startOfWeek(DateTime.now()),
              )
              .first,
        );
        expect(survivors!.single.recipeTitle, 'Weeknight Curry');
      },
    );

    gleanWidgetTest(
      'a mark-cooked failure is caught and surfaced, leaving the entry '
      'uncooked',
      (WidgetTester tester) async {
        final throwingRepo = _ThrowingMarkCookedPlanRepository(
          harness.db,
          pantry,
        );
        final recipeId = await saveRecipe('Weeknight Curry');
        await throwingRepo.addEntry(
          userId: harness.userId,
          recipeId: recipeId,
          recipeTitle: 'Weeknight Curry',
          servings: 2,
        );
        final localHarness = AppTestHarness(
          overrides: [planRepositoryProvider.overrideWithValue(throwingRepo)],
        );
        addTearDown(() => localHarness.dispose());

        await localHarness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
        await tester.pumpAndSettle();

        expect(find.textContaining('Could not mark'), findsOneWidget);
        expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);
      },
    );

    gleanWidgetTest('an undo-cooked failure is caught and surfaced', (
      WidgetTester tester,
    ) async {
      final throwingRepo = _ThrowingUndoCookedPlanRepository(
        harness.db,
        pantry,
      );
      final recipeId = await saveRecipe('Weeknight Curry');
      await throwingRepo.addEntry(
        userId: harness.userId,
        recipeId: recipeId,
        recipeTitle: 'Weeknight Curry',
        servings: 2,
      );
      final localHarness = AppTestHarness(
        overrides: [planRepositoryProvider.overrideWithValue(throwingRepo)],
      );
      addTearDown(() => localHarness.dispose());

      await localHarness.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Could not undo cooking'), findsOneWidget);
    });

    gleanWidgetTest(
      'marking cooked decrements pantry, transitions to a checkmark, and '
      'undo restores the exact quantity (AC-UX-03, AC-PLAN-13)',
      (WidgetTester tester) async {
        await pantry.addItem(
          userId: harness.userId,
          name: 'chicken breast',
          quantity: 500,
          unit: 'g',
          category: 'poultry',
        );
        final id = await saveRecipe(
          'Chicken Dinner',
          ingredients: const <SaveRecipeIngredient>[
            SaveRecipeIngredient(
              canonicalName: 'chicken breast',
              quantity: 200,
              unit: 'g',
            ),
          ],
        );
        await plan.addEntry(
          userId: harness.userId,
          recipeId: id,
          recipeTitle: 'Chicken Dinner',
          servings: 1,
        );

        await harness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();
        expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);

        await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
        await tester.pumpAndSettle();

        expect(find.text('Chicken Dinner marked as cooked'), findsOneWidget);
        expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsNothing);
        expect(find.byIcon(Icons.check_rounded), findsOneWidget);
        // The pill/checkmark swap goes through AnimatedSwitcher (AC-PLAN-13)
        // — never a bare conditional with no transition machinery at all.
        expect(find.byType(AnimatedSwitcher), findsWidgets);
        var pantryItems = await tester.runAsync(
          () => pantry.watchAll(harness.userId).first,
        );
        expect(pantryItems!.single.quantity, 300); // 500 - 200

        await tester.tap(find.text('Undo'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);
        pantryItems = await tester.runAsync(
          () => pantry.watchAll(harness.userId).first,
        );
        expect(pantryItems!.single.quantity, 500);
      },
    );

    gleanWidgetTest(
      'Generate disables itself while a generation is pending, so a '
      'double-tap cannot overfill (AC-PLAN-09)',
      (WidgetTester tester) async {
        final mockHttp = MockHttpClient();
        final localHarness = AppTestHarness(httpClient: mockHttp);
        addTearDown(() => localHarness.dispose());
        final localIngredients = IngredientsRepository(localHarness.db);
        final localRecipes = RecipesRepository(
          localHarness.db,
          localIngredients,
        );
        final localPlan = PlanRepository(
          localHarness.db,
          PantryRepository(localHarness.db, localIngredients),
        );
        final localConfig = UserConfigRepository(localHarness.db);

        final recipeId = await localRecipes.save(
          userId: localHarness.userId,
          title: 'Suggested Dish',
          ingredients: const <SaveRecipeIngredient>[],
        );
        await localConfig.save(
          UserConfigView(
            id: localHarness.userId,
            purchaseTolerance: 0.5,
            preferredServings: 2,
            mealsPerWeek: 1,
            dietaryFlags: const <String>[],
            maxActiveTimeMins: null,
          ),
        );

        final completer = Completer<http.Response>();
        when(
          () => mockHttp.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) => completer.future);

        await localHarness.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();

        await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
        await tester.pump();

        final FilledButton pendingButton = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Generating'),
        );
        expect(
          pendingButton.onPressed,
          isNull,
          reason: 'disabled while pending — a second tap can reach nothing',
        );

        completer.complete(
          http.Response(
            jsonEncode(<String, Object?>{
              'suggestions': <Map<String, Object?>>[
                <String, Object?>{
                  'recipe_id': recipeId,
                  'title': 'Suggested Dish',
                  'reason': 'ok',
                  'missing_ingredients': <String>[],
                },
              ],
            }),
            200,
            headers: const <String, String>{'content-type': 'application/json'},
          ),
        );
        // Bounded pumps, not `pumpAndSettle`: once generation resolves the
        // progress ring animates and a snackbar is on screen, and the plan's
        // skeleton animates perpetually by design (AC-DS-11), so there is no
        // quiescent frame for `pumpAndSettle` to find — it times out, which
        // reads as a hang rather than a failure.
        await pumpUntil(
          tester,
          () => find.text('Week generated').evaluate().isNotEmpty,
          description: 'the generation-complete snackbar',
        );

        verify(
          () => mockHttp.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).called(1);
        expect(find.text('Week generated'), findsOneWidget);
        // A one-shot read, not `.watch().first`: no stream subscription to
        // open and tear down, so unlike the other assertions in this file,
        // this needs no `tester.runAsync` escape from the FakeAsync zone.
        final entries = await localPlan.getWeek(
          userId: localHarness.userId,
          weekStart: startOfWeek(DateTime.now()),
        );
        expect(entries, hasLength(1));
      },
    );
  });
}
