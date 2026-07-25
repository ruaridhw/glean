// Real-outcome tests for the saved-recipe library (AC-TEST-02), including
// the two RN bugs FLUTTER_MIGRATION.md §11 calls out by name:
// `getRecipeByExternalId` skipping `attachDietaryFlags` (AC-MEAL-13), and
// recipe deletion destroying a plan entry's record of what was cooked
// (AC-MEAL-03).
import 'package:glean/data/database.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('RecipesRepository', () {
    late GleanDatabase db;
    late RecipesRepository repository;
    late PlanRepository planRepository;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      repository = RecipesRepository(db, IngredientsRepository(db));
      planRepository = PlanRepository(
        db,
        PantryRepository(db, IngredientsRepository(db)),
      );
    });

    tearDown(() => db.close());

    Future<int> saveSampleRecipe({String externalId = 'ext-1'}) {
      return repository.save(
        userId: userId,
        externalId: externalId,
        title: 'Tomato Pasta',
        dietaryFlags: const ['vegetarian', 'dairy_free'],
        notSuitableFor: const ['nuts'],
        instructions: const [
          RecipeInstructionStep(
            stepNumber: 1,
            phase: 'prep',
            text: 'Chop onions',
          ),
        ],
        ingredients: const [
          SaveRecipeIngredient(
            canonicalName: 'pasta',
            quantity: 200,
            unit: 'g',
          ),
          SaveRecipeIngredient(
            canonicalName: 'tomato',
            apiIngredientId: 'api-tomato',
            quantity: 3,
            unit: 'unit',
          ),
        ],
      );
    }

    test(
      'save persists the recipe, its ingredients, flags and instructions',
      () async {
        final id = await saveSampleRecipe();

        final recipe = await repository.getById(id: id, userId: userId);
        expect(recipe, isNotNull);
        expect(recipe!.title, 'Tomato Pasta');
        expect(
          recipe.dietaryFlags,
          unorderedEquals(['vegetarian', 'dairy_free']),
        );
        expect(recipe.notSuitableFor, ['nuts']);
        expect(recipe.instructions.single.text, 'Chop onions');

        final ingredients = await repository.getIngredients(id);
        expect(ingredients, hasLength(2));
        expect(ingredients.map((i) => i.ingredient.canonicalName).toSet(), {
          'pasta',
          'tomato',
        });
      },
    );

    test(
      'getByExternalId attaches dietary flags like getById and getSavedRecipes (AC-MEAL-13)',
      () async {
        await saveSampleRecipe(externalId: 'ext-42');

        final recipe = await repository.getByExternalId(
          externalId: 'ext-42',
          userId: userId,
        );

        expect(recipe, isNotNull);
        expect(
          recipe!.dietaryFlags,
          unorderedEquals(['vegetarian', 'dairy_free']),
        );
      },
    );

    test('watchSaved lists the user\'s recipes newest first', () async {
      final firstId = await saveSampleRecipe(externalId: 'ext-a');
      final secondId = await saveSampleRecipe(externalId: 'ext-b');

      final saved = await repository.watchSaved(userId).first;

      expect(saved.map((r) => r.id).toList(), [secondId, firstId]);
    });

    test(
      'deleteRecipe keeps a referencing plan entry and only clears the link (AC-MEAL-03)',
      () async {
        final plannedDate = DateTime(2026, 1, 5);
        final recipeId = await saveSampleRecipe();
        final entryId = await planRepository.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Tomato Pasta',
          servings: 2,
          plannedDate: plannedDate,
        );

        await repository.deleteRecipe(id: recipeId, userId: userId);

        expect(await repository.getById(id: recipeId, userId: userId), isNull);

        final entries = await planRepository
            .watchWeek(userId: userId, weekStart: startOfWeek(plannedDate))
            .first;
        final entry = entries.singleWhere((e) => e.id == entryId);
        expect(entry.recipeId, isNull);
        expect(entry.recipeTitle, 'Tomato Pasta');
      },
    );
  });
}
