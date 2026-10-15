// Every frozen older database file must still open on the current schema with the owner's data intact. A new
// schema version adds its fixture to the list below.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/store_section.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:sqlite3/sqlite3.dart';

void main() {
  for (final int fixtureVersion in <int>[1, 2]) {
    test('a version $fixtureVersion file upgrades with its recipes and '
        'ingredients intact, and the store section of a row can be moved '
        'and survives a reopen', () async {
      final directory = await Directory.systemTemp.createTemp('glean-upgrade-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/glean.sqlite');
      final raw = sqlite3.open(file.path);
      raw.execute(
        File(
          'test/data/fixtures/schema_v$fixtureVersion.sql',
        ).readAsStringSync(),
      );
      raw.close();

      var db = GleanDatabase(NativeDatabase(file));
      final ingredients = IngredientsRepository(db);
      final recipes = RecipesRepository(db, ingredients);
      final recipe = await recipes.getByExternalId(
        userId: 'reopen-user',
        externalId: 'rec_persist',
      );
      expect(recipe?.title, 'Persisted dinner');
      expect((await db.select(db.ingredients).get()).length, greaterThan(9));

      expect(
        await UserConfigRepository(
          db,
        ).watchGroupShoppingBySection('reopen-user').first,
        isFalse,
      );

      final shopping = ShoppingRepository(db, ingredients);
      final pepper = await ingredients.resolveOrCreate(
        canonicalName: 'black pepper',
      );
      if (fixtureVersion == 2) {
        final rows = await shopping.watchAll('reopen-user').first;
        expect(rows.single.name, 'black pepper');
        expect(rows.single.section, StoreSection.foodCupboard);
      }
      await shopping.moveToSection(
        ingredientId: pepper.id,
        section: StoreSection.baking,
      );
      await db.close();

      db = GleanDatabase(NativeDatabase(file));
      addTearDown(db.close);
      await db.customSelect('SELECT 1').get();
      final reopened = await ShoppingRepository(
        db,
        IngredientsRepository(db),
      ).addManualItem(userId: 'reopen-user', name: 'Black pepper');
      final row = (await ShoppingRepository(
        db,
        IngredientsRepository(db),
      ).watchAll('reopen-user').first).firstWhere((i) => i.id == reopened);
      expect(row.section, StoreSection.baking);
    });
  }
}
