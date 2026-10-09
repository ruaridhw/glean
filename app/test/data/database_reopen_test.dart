import 'dart:io';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:sqlite3/sqlite3.dart';

void main() {
  test(
    'a real version-one file reopens with user data, unique seeds and enforcing foreign keys',
    () async {
      final directory = await Directory.systemTemp.createTemp('glean-reopen-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/glean.sqlite');
      final raw = sqlite3.open(file.path);
      raw.execute(File('test/data/fixtures/schema_v1.sql').readAsStringSync());
      raw.close();
      for (var reopen = 0; reopen < 2; reopen++) {
        final db = GleanDatabase(NativeDatabase(file));
        final recipes = RecipesRepository(db, IngredientsRepository(db));
        final recipe = await recipes.getByExternalId(
          userId: 'reopen-user',
          externalId: 'rec_persist',
        );
        expect(recipe?.title, 'Persisted dinner');
        expect((await recipes.getIngredients(recipe!.id)).single.quantity, 200);
        final categories = await db.select(db.ingredientCategories).get();
        expect(
          categories.map((c) => c.category).toSet().length,
          categories.length,
        );
        expect(categories, hasLength(23));
        expect(
          (await db.select(db.ingredients).get()).where((i) => i.isStaple),
          hasLength(10),
        );
        expect(
          (await db.customSelect('PRAGMA foreign_keys').getSingle())
              .data
              .values
              .single,
          1,
        );
        if (reopen == 1) {
          await recipes.deleteRecipe(id: recipe.id, userId: 'reopen-user');
          expect(
            (await db.select(db.mealPlanEntries).get()).single.recipeId,
            isNull,
          );
        }
        await db.close();
      }
    },
  );
}
