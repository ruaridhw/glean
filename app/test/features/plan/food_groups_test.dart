// Coverage for AC-PLAN-08: `food_groups`/`food_group_coverage` must be
// computed for real from the pantry/plan, not hardcoded empty the way RN's
// client did (which permanently disabled the backend's food-group-balancing
// prompt rule).
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/food_groups.dart';

import '../../data/fixture.dart';

void main() {
  group('foodGroupForCategory', () {
    test('resolves a known category to its taxonomy food group', () {
      expect(foodGroupForCategory('poultry'), 'protein');
      expect(foodGroupForCategory('leafy_greens'), 'vegetables');
    });

    test('falls back to "other" for null or unrecognised categories', () {
      expect(foodGroupForCategory(null), uncategorisedFoodGroup);
      expect(
        foodGroupForCategory('not-a-real-category'),
        uncategorisedFoodGroup,
      );
    });
  });

  group('foodGroupsForRecipe / foodGroupCoverageForWeek', () {
    late GleanDatabase db;
    late RecipesRepository recipes;
    late PlanRepository plan;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      final ingredients = IngredientsRepository(db);
      recipes = RecipesRepository(db, ingredients);
      plan = PlanRepository(db, PantryRepository(db, ingredients));
    });

    tearDown(() => db.close());

    test('a recipe\'s food groups are computed from its ingredients\' '
        'categories, non-empty for a real recipe (AC-PLAN-08)', () async {
      final recipeId = await recipes.save(
        userId: userId,
        title: 'Chicken and rice',
        ingredients: const <SaveRecipeIngredient>[
          SaveRecipeIngredient(
            canonicalName: 'chicken breast',
            quantity: 200,
            unit: 'g',
          ),
        ],
      );
      // Give the ingredient a real category the way pantry/shopping
      // intake would (recipe import alone leaves it uncategorised, §9).
      await IngredientsRepository(
        db,
      ).resolveOrCreate(canonicalName: 'chicken breast', category: 'poultry');

      final groups = await foodGroupsForRecipe(recipes, recipeId);
      expect(groups, <String>['protein']);
    });

    test(
      'an ingredient with no category degrades to "other" rather than throwing',
      () async {
        final recipeId = await recipes.save(
          userId: userId,
          title: 'Mystery bake',
          ingredients: const <SaveRecipeIngredient>[
            SaveRecipeIngredient(
              canonicalName: 'mystery ingredient',
              quantity: 1,
              unit: 'unit',
            ),
          ],
        );

        final groups = await foodGroupsForRecipe(recipes, recipeId);
        expect(groups, <String>[uncategorisedFoodGroup]);
      },
    );

    test('coverage tallies only cooked entries, skipping deleted-recipe and '
        'unknown-food-group entries', () async {
      final chickenId = await recipes.save(
        userId: userId,
        title: 'Chicken dinner',
        ingredients: const <SaveRecipeIngredient>[],
      );
      final riceId = await recipes.save(
        userId: userId,
        title: 'Rice bowl',
        ingredients: const <SaveRecipeIngredient>[],
      );
      final week = startOfWeek(DateTime(2026, 1, 5));

      final cookedEntry = await plan.addEntry(
        userId: userId,
        recipeId: chickenId,
        recipeTitle: 'Chicken dinner',
        servings: 1,
        plannedDate: week,
      );
      await plan.markCooked(
        entryId: cookedEntry,
        userId: userId,
        now: DateTime(2026, 1, 6),
      );
      // Uncooked — must not count yet.
      await plan.addEntry(
        userId: userId,
        recipeId: riceId,
        recipeTitle: 'Rice bowl',
        servings: 1,
        plannedDate: week,
      );

      final entries = await plan
          .watchWeek(userId: userId, weekStart: week)
          .first;
      final coverage = foodGroupCoverageForWeek(entries, <int, List<String>>{
        chickenId: <String>['protein'],
        riceId: <String>['carbohydrates'],
      });

      expect(coverage, <String, int>{'protein': 1});
    });

    test('a recipe covering multiple food groups increments each of them', () {
      final entry = MealPlanEntryView(
        id: 1,
        userId: userId,
        recipeId: 10,
        recipeTitle: 'Chicken and rice bake',
        plannedDate: DateTime(2026, 1, 5),
        cookedAt: DateTime(2026, 1, 6),
        servings: 2,
      );
      final coverage = foodGroupCoverageForWeek(
        <MealPlanEntryView>[entry],
        <int, List<String>>{
          10: <String>['protein', 'carbohydrates'],
        },
      );
      expect(coverage, <String, int>{'protein': 1, 'carbohydrates': 1});
    });
  });
}
