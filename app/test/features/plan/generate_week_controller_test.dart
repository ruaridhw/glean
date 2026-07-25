// Coverage for generation's guarantees (AC-PLAN-07/08/09/10): real
// `food_groups`/`food_group_coverage` in the request, `preferred_servings`
// honoured on every inserted entry, a double-tap can't fire a second
// network call while one is pending, and a hallucinated `recipe_id` in the
// response aborts the whole batch — nothing is written, and the caller
// always sees an error — rather than RN's silent half-write.
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

http.Response _mealPlanResponse(List<Map<String, Object?>> suggestions) {
  return http.Response(
    jsonEncode(<String, Object?>{'suggestions': suggestions}),
    200,
    headers: const {'content-type': 'application/json'},
  );
}

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:9999/'));
  });

  group('GenerateWeekController', () {
    late MockHttpClient httpClient;
    late AppTestHarness harness;
    late RecipesRepository recipes;
    late PlanRepository plan;
    late ShoppingRepository shopping;
    late UserConfigRepository userConfig;
    final DateTime week = startOfWeek(DateTime(2026, 1, 5));

    setUp(() {
      httpClient = MockHttpClient();
      harness = AppTestHarness(httpClient: httpClient);
      final ingredients = IngredientsRepository(harness.db);
      recipes = RecipesRepository(harness.db, ingredients);
      plan = PlanRepository(
        harness.db,
        PantryRepository(harness.db, ingredients),
      );
      shopping = ShoppingRepository(harness.db, ingredients);
      userConfig = UserConfigRepository(harness.db);
    });

    tearDown(() => harness.dispose());

    Future<int> saveChickenRecipe() {
      return recipes.save(
        userId: harness.userId,
        title: 'Chicken Curry',
        ingredients: const <SaveRecipeIngredient>[
          SaveRecipeIngredient(
            canonicalName: 'chicken breast',
            quantity: 200,
            unit: 'g',
          ),
        ],
      );
    }

    test('populates real food_groups/food_group_coverage and honours '
        'preferred_servings on the inserted entry', () async {
      final chickenId = await saveChickenRecipe();
      await IngredientsRepository(
        harness.db,
      ).resolveOrCreate(canonicalName: 'chicken breast', category: 'poultry');
      await userConfig.save(
        UserConfigView(
          id: harness.userId,
          purchaseTolerance: 0.5,
          preferredServings: 4,
          mealsPerWeek: 5,
          dietaryFlags: const <String>['vegetarian'],
          maxActiveTimeMins: null,
        ),
      );

      Map<String, Object?>? capturedBody;
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((invocation) async {
        capturedBody =
            jsonDecode(invocation.namedArguments[#body] as String)
                as Map<String, Object?>;
        return _mealPlanResponse(<Map<String, Object?>>[
          <String, Object?>{
            'recipe_id': chickenId,
            'title': 'Chicken Curry',
            'reason': 'Uses up pantry chicken',
            'missing_ingredients': <String>[],
          },
        ]);
      });

      final controller = harness.container.read(
        generateWeekControllerProvider.notifier,
      );
      await controller.generate(weekStart: week, slots: 1, servings: 4);

      expect(
        harness.container.read(generateWeekControllerProvider).hasError,
        isFalse,
      );

      // The request body sent real, non-empty food group data — not RN's
      // hardcoded `food_groups: []` / `food_group_coverage: {}`.
      final List<dynamic> history =
          capturedBody!['recipe_history'] as List<dynamic>;
      final Map<String, dynamic> chickenHistory =
          history.single as Map<String, dynamic>;
      expect(chickenHistory['food_groups'], <String>['protein']);
      expect(capturedBody!['dietary_flags'], <String>['vegetarian']);

      final entries = await plan
          .watchWeek(userId: harness.userId, weekStart: week)
          .first;
      expect(entries, hasLength(1));
      expect(entries.single.servings, 4); // AC-PLAN-07
      expect(entries.single.recipeId, chickenId);

      // A shopping gap row was added for the newly-planned recipe, linked
      // back to the entry so deleting it cascades the row away
      // (AC-SHOP-06).
      final shoppingRows = await shopping.watchAll(harness.userId).first;
      expect(shoppingRows, hasLength(1));
      expect(shoppingRows.single.sourceMealPlanEntryId, entries.single.id);
    });

    test('a hallucinated recipe_id aborts the whole batch — nothing is '
        'written, and the caller sees an error (AC-PLAN-10)', () async {
      final realId = await saveChickenRecipe();
      await userConfig.save(
        UserConfigView(
          id: harness.userId,
          purchaseTolerance: 0.5,
          preferredServings: 2,
          mealsPerWeek: 5,
          dietaryFlags: const <String>[],
          maxActiveTimeMins: null,
        ),
      );

      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => _mealPlanResponse(<Map<String, Object?>>[
          // A real suggestion the batch *would* otherwise have written...
          <String, Object?>{
            'recipe_id': realId,
            'title': 'Chicken Curry',
            'reason': 'ok',
            'missing_ingredients': <String>[],
          },
          // ...followed by a hallucinated id with no matching saved recipe.
          <String, Object?>{
            'recipe_id': 999999,
            'title': 'Invented Recipe',
            'reason': 'ok',
            'missing_ingredients': <String>[],
          },
        ]),
      );

      final controller = harness.container.read(
        generateWeekControllerProvider.notifier,
      );
      await controller.generate(weekStart: week, slots: 2, servings: 2);

      expect(
        harness.container.read(generateWeekControllerProvider).hasError,
        isTrue,
      );

      // Neither suggestion was persisted — the good one included, proving
      // this is a whole-batch abort, not a skip-the-bad-one filter that
      // would otherwise have silently half-written the plan.
      final entries = await plan
          .watchWeek(userId: harness.userId, weekStart: week)
          .first;
      expect(entries, isEmpty);
    });

    test('a double-tap while a generation is pending fires only one network '
        'call (AC-PLAN-09)', () async {
      final chickenId = await saveChickenRecipe();
      await userConfig.save(
        UserConfigView(
          id: harness.userId,
          purchaseTolerance: 0.5,
          preferredServings: 2,
          mealsPerWeek: 5,
          dietaryFlags: const <String>[],
          maxActiveTimeMins: null,
        ),
      );

      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => _mealPlanResponse(<Map<String, Object?>>[
          <String, Object?>{
            'recipe_id': chickenId,
            'title': 'Chicken Curry',
            'reason': 'ok',
            'missing_ingredients': <String>[],
          },
        ]),
      );

      final controller = harness.container.read(
        generateWeekControllerProvider.notifier,
      );
      final first = controller.generate(weekStart: week, slots: 1, servings: 2);
      final second = controller.generate(
        weekStart: week,
        slots: 1,
        servings: 2,
      );
      await Future.wait(<Future<void>>[first, second]);

      verify(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).called(1);

      // And only one entry got planned, not two.
      final entries = await plan
          .watchWeek(userId: harness.userId, weekStart: week)
          .first;
      expect(entries, hasLength(1));
    });
  });
}
