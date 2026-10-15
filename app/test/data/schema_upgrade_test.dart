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

  for (final int fixtureVersion in <int>[1, 2]) {
    test('a version $fixtureVersion file keeps every row of every table, '
        'including its settings, history and cooked adjustments, and the new '
        'columns start unset', () async {
      final directory = await Directory.systemTemp.createTemp('glean-keep-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/glean.sqlite');
      final old = sqlite3.open(file.path);
      old.execute(
        File(
          'test/data/fixtures/schema_v$fixtureVersion.sql',
        ).readAsStringSync(),
      );
      // The frozen file has no settings or history, so add representative
      // owner data using only columns that exist in both old versions.
      old.execute("""
        INSERT INTO user_config (id, purchase_tolerance, preferred_servings,
          meals_per_week, dietary_flags, max_active_time_mins,
          onboarding_completed)
        VALUES ('reopen-user', 0.7, 4, 3, '["vegetarian"]', 45, 1);
        INSERT INTO recipe_dietary_flags (recipe_id, flag)
        VALUES (1, 'gluten_free');
        INSERT INTO pantry_items (user_id, ingredient_id, quantity, unit,
          unit_price, expiry_date, last_used_at, updated_at)
        VALUES ('reopen-user', 6, 250, 'g', 1.85, '2026-10-20',
          '2026-10-06T18:00:00Z', '2026-10-07T12:00:00Z');
        INSERT INTO meal_plan_entries (user_id, recipe_id, recipe_title,
          planned_date, cooked_at, servings)
        VALUES ('reopen-user', 1, 'Persisted dinner', '2026-10-03',
          '2026-10-03T19:30:00Z', 2);
        INSERT INTO cooked_adjustments (user_id, meal_plan_entry_id,
          ingredient_id, amount_deducted, unit, previous_last_used_at,
          created_at)
        VALUES ('reopen-user', 2, 11, 200, 'g', NULL,
          '2026-10-03T19:30:01Z');
        INSERT INTO shopping_list_items (user_id, ingredient_id, name,
          quantity, unit, source, is_checked, source_meal_plan_entry_id)
        VALUES ('reopen-user', 11, 'chicken breast', 200, 'g', 'meal_plan',
          1, 1);
      """);

      // Every old table with all its old columns, exactly as stored.
      final Map<String, List<String>> columns = <String, List<String>>{
        for (final Row table in old.select(
          "SELECT name FROM sqlite_master WHERE type = 'table' "
          "AND name NOT LIKE 'sqlite_%'",
        ))
          table['name'] as String: <String>[
            for (final Row c in old.select(
              'PRAGMA table_info("${table['name']}")',
            ))
              c['name'] as String,
          ],
      };
      List<List<Object?>> rowsOf(Database d, String table) => <List<Object?>>[
        for (final Row r in d.select(
          'SELECT ${columns[table]!.map((c) => '"$c"').join(', ')} '
          'FROM "$table" ORDER BY rowid',
        ))
          r.values,
      ];
      final Map<String, List<List<Object?>>> before =
          <String, List<List<Object?>>>{
            for (final String table in columns.keys) table: rowsOf(old, table),
          };
      old.close();
      expect(before['user_config'], hasLength(1));
      expect(before['pantry_items'], hasLength(2));
      expect(before['meal_plan_entries'], hasLength(2));
      expect(before['cooked_adjustments'], hasLength(1));
      expect(
        before['shopping_list_items']!.length,
        fixtureVersion == 2 ? 2 : 1,
      );

      final db = GleanDatabase(NativeDatabase(file));
      await db.customSelect('SELECT 1').get();
      await db.close();

      final upgraded = sqlite3.open(file.path);
      addTearDown(upgraded.close);
      expect(upgraded.select('PRAGMA user_version').single.values.single, 5);
      for (final String table in columns.keys) {
        expect(
          rowsOf(upgraded, table),
          before[table],
          reason: 'every row of $table keeps its old column values',
        );
      }

      // Independent literals for the owner-visible rows.
      expect(
        upgraded
            .select(
              'SELECT purchase_tolerance, preferred_servings, meals_per_week, '
              'dietary_flags, max_active_time_mins, onboarding_completed, '
              'group_shopping_by_section FROM user_config',
            )
            .single
            .values,
        <Object?>[0.7, 4, 3, '["vegetarian"]', 45, 1, 0],
      );
      expect(
        upgraded
            .select(
              'SELECT ingredient_id, quantity, unit, unit_price, expiry_date '
              'FROM pantry_items ORDER BY id',
            )
            .map((Row r) => r.values)
            .toList(),
        <List<Object?>>[
          <Object?>[11, 500.0, 'g', null, '2026-10-09'],
          <Object?>[6, 250.0, 'g', 1.85, '2026-10-20'],
        ],
      );
      expect(
        upgraded
            .select(
              'SELECT recipe_title, planned_date, cooked_at FROM meal_plan_entries '
              'ORDER BY id',
            )
            .map((Row r) => r.values)
            .toList(),
        <List<Object?>>[
          <Object?>['Persisted dinner', '2026-10-05', null],
          <Object?>['Persisted dinner', '2026-10-03', '2026-10-03T19:30:00Z'],
        ],
      );
      expect(
        upgraded
            .select(
              'SELECT meal_plan_entry_id, amount_deducted, unit '
              'FROM cooked_adjustments',
            )
            .single
            .values,
        <Object?>[2, 200.0, 'g'],
      );
      expect(
        upgraded.select('SELECT title FROM recipes').single.values,
        <Object?>['Persisted dinner'],
      );
      expect(
        upgraded.select('SELECT flag FROM recipe_dietary_flags').single.values,
        <Object?>['gluten_free'],
      );
      expect(
        upgraded
            .select(
              'SELECT name, quantity, unit, is_checked FROM shopping_list_items '
              "WHERE source = 'meal_plan'",
            )
            .single
            .values,
        <Object?>['chicken breast', 200.0, 'g', 1],
      );
      expect(
        upgraded
            .select(
              'SELECT count(*) FROM ingredients WHERE store_section IS NOT NULL',
            )
            .single
            .values
            .single,
        0,
      );
    });
  }
}
