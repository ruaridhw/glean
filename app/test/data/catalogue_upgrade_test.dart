// Every frozen older database file must reopen on the current schema with all of the owner's rows identical, now
// with the catalogue tables beside them: empty except for the seeded ingredient groups, or, from a version that
// already synced a catalogue, still holding those rows with no section until the next sync. The household's override
// and redirect tables start empty.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:sqlite3/sqlite3.dart';

const List<String> _householdCatalogueTables = <String>[
  'ingredient_overrides',
  'catalogue_item_redirects',
];

List<List<Object?>> _rowsOf(
  Database database,
  String table,
  List<String> columns,
) => <List<Object?>>[
  for (final Row row in database.select(
    'SELECT ${columns.map((c) => '"$c"').join(', ')} FROM "$table" ORDER BY rowid',
  ))
    row.values,
];

void main() {
  for (final int fixtureVersion in <int>[1, 2, 3, 4]) {
    test('a version $fixtureVersion file upgrades with every row of every old '
        'table identical and the new catalogue tables in place', () async {
      final directory = await Directory.systemTemp.createTemp('glean-cat-up-');
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
      // (The v3 file already holds its own settings row, with grouping on, which must be left as it is.)
      old.execute("""
        INSERT OR IGNORE INTO user_config (id, purchase_tolerance, preferred_servings,
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
      // The two tables this version rewrote: the ingredient group migration has its own tests, and here only the
      // columns that survive it are compared.
      columns.remove('ingredient_categories');
      columns['ingredients'] = <String>[
        for (final String c in columns['ingredients']!)
          if (c != 'category' && c != 'api_ingredient_id') c,
      ];
      final Map<String, List<List<Object?>>> before =
          <String, List<List<Object?>>>{
            for (final String table in columns.keys)
              table: _rowsOf(old, table, columns[table]!),
          };
      if (fixtureVersion >= 3) {
        // Independent literals for #155's data, so the equality check below cannot pass on two empty reads.
        expect(
          old
              .select('SELECT store_section FROM ingredients WHERE id = 3')
              .single
              .values
              .single,
          'baking',
        );
        expect(
          old
              .select('SELECT group_shopping_by_section FROM user_config')
              .single
              .values
              .single,
          1,
        );
      }
      old.close();
      expect(before['pantry_items'], hasLength(2));
      expect(before['meal_plan_entries'], hasLength(2));
      expect(before['cooked_adjustments'], hasLength(1));
      expect(before['user_config'], hasLength(1));
      expect(before['ingredients'], hasLength(11));

      // Opened twice: the second open must not touch anything again.
      for (var open = 0; open < 2; open++) {
        final db = GleanDatabase(NativeDatabase(file));
        await db.customSelect('SELECT 1').get();
        await db.close();
      }

      final upgraded = sqlite3.open(file.path);
      addTearDown(upgraded.close);
      expect(upgraded.select('PRAGMA user_version').single.values.single, 6);
      for (final String table in columns.keys) {
        expect(
          _rowsOf(upgraded, table, columns[table]!),
          before[table],
          reason: 'every row of $table keeps its old column values',
        );
      }
      expect(
        upgraded
            .select('SELECT count(*) FROM ingredient_groups')
            .single
            .values
            .single,
        29,
      );
      if (fixtureVersion >= 3) {
        expect(
          upgraded
              .select('SELECT store_section FROM ingredients WHERE id = 3')
              .single
              .values
              .single,
          'baking',
          reason:
              'the household\'s own section move for black pepper survives the upgrade',
        );
        expect(
          upgraded
              .select('SELECT group_shopping_by_section FROM user_config')
              .single
              .values
              .single,
          1,
          reason: 'grouping by section stays on',
        );
      }
      final int syncedItems = fixtureVersion < 4 ? 0 : 3;
      expect(
        upgraded
            .select('SELECT count(*) FROM catalogue_items')
            .single
            .values
            .single,
        syncedItems,
      );
      expect(
        upgraded
            .select(
              'SELECT count(*) FROM catalogue_items WHERE section IS NULL',
            )
            .single
            .values
            .single,
        syncedItems,
        reason: 'no item has a section until the next sync delivers it',
      );
      for (final String table in <String>[
        ..._householdCatalogueTables,
        if (fixtureVersion < 4) ...<String>[
          'catalogue_aliases',
          'catalogue_sync_state',
        ],
      ]) {
        expect(
          upgraded.select('SELECT count(*) FROM $table').single.values.single,
          0,
          reason: '$table starts empty',
        );
      }
    });
  }
}
