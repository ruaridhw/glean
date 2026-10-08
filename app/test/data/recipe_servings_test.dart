import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';

import 'fixture.dart';

void main() {
  for (final yieldCount in [4, null, 0, -1]) {
    test(
      'shopping scales whole-recipe amounts with yield $yieldCount',
      () async {
        final db = createTestDatabase();
        addTearDown(db.close);
        final ingredients = IngredientsRepository(db);
        final pantry = PantryRepository(db, ingredients);
        final recipes = RecipesRepository(db, ingredients);
        final plan = PlanRepository(db, pantry);
        final shopping = ShoppingRepository(db, ingredients);
        final id = await recipes.save(
          userId: 'owner',
          title: 'Four-serving beef recipe',
          yieldCount: yieldCount,
          ingredients: const [
            SaveRecipeIngredient(
              canonicalName: 'beef',
              quantity: 500,
              unit: 'g',
            ),
          ],
        );
        final entry = await plan.addEntry(
          userId: 'owner',
          recipeId: id,
          recipeTitle: 'Beef',
          servings: 2,
        );
        await shopping.addGapsForRecipe(
          userId: 'owner',
          recipeId: id,
          servings: 2,
          sourceMealPlanEntryId: entry,
        );
        final rows = await db.select(db.shoppingListItems).get();
        expect(rows.single.quantity, yieldCount == 4 ? 250 : 1000);
      },
    );
  }

  test(
    'gap is scaled demand minus stock, but cooking consumes full scaled demand',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final ingredients = IngredientsRepository(db);
      final pantry = PantryRepository(db, ingredients);
      final recipes = RecipesRepository(db, ingredients);
      final plan = PlanRepository(db, pantry);
      final shopping = ShoppingRepository(db, ingredients);
      final id = await recipes.save(
        userId: 'owner',
        title: 'Four-serving beef recipe',
        yieldCount: 4,
        ingredients: const [
          SaveRecipeIngredient(canonicalName: 'beef', quantity: 500, unit: 'g'),
        ],
      );
      await pantry.addItem(
        userId: 'owner',
        name: 'beef',
        quantity: 175,
        unit: 'g',
        category: 'red_meat',
      );
      final entry = await plan.addEntry(
        userId: 'owner',
        recipeId: id,
        recipeTitle: 'Beef',
        servings: 2,
      );
      await shopping.addGapsForRecipe(
        userId: 'owner',
        recipeId: id,
        servings: 2,
        sourceMealPlanEntryId: entry,
      );
      expect((await shopping.watchAll('owner').first).single.quantity, 75);
      await plan.markCooked(entryId: entry, userId: 'owner');
      expect((await db.select(db.pantryItems).get()).single.quantity, 0);
      await plan.undoCooked(entryId: entry, userId: 'owner');
      expect((await db.select(db.pantryItems).get()).single.quantity, 175);
    },
  );

  test(
    'two servings of a four-serving recipe consume 250g and Undo restores 1100g',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final ingredients = IngredientsRepository(db);
      final pantry = PantryRepository(db, ingredients);
      final recipes = RecipesRepository(db, ingredients);
      final plan = PlanRepository(db, pantry);
      final id = await recipes.save(
        userId: 'owner',
        title: 'Four-serving beef recipe',
        yieldCount: 4,
        ingredients: const [
          SaveRecipeIngredient(canonicalName: 'beef', quantity: 500, unit: 'g'),
        ],
      );
      await pantry.addItem(
        userId: 'owner',
        name: 'beef',
        quantity: 1100,
        unit: 'g',
        category: 'red_meat',
      );
      final entry = await plan.addEntry(
        userId: 'owner',
        recipeId: id,
        recipeTitle: 'Beef',
        servings: 2,
      );
      await plan.markCooked(entryId: entry, userId: 'owner');
      expect((await db.select(db.pantryItems).get()).single.quantity, 850);
      await plan.undoCooked(entryId: entry, userId: 'owner');
      final restored = (await db.select(db.pantryItems).get()).single;
      expect(restored.quantity, 1100);
      expect(restored.lastUsedAt, isNull);
    },
  );
}
