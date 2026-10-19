// The upgrade that moves ingredients from the 23 old categories onto ingredient groups rewrites existing rows, so
// every frozen older database file is opened here and checked row by row: nothing the owner has is lost, the old
// categories read under their group's name, and an ingredient the catalogue doesn't know keeps working.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/store_section.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:sqlite3/sqlite3.dart';

// Written out here, not read from the code under test, so the mapping can't agree with itself by construction.
const Map<String, String> _groupOfOldCategory = <String, String>{
  'leafy_greens': 'leafy_greens',
  'brassicas': 'cabbage_and_broccoli',
  'alliums': 'onions_and_garlic',
  'root_vegetables': 'root_veg',
  'nightshades': 'tomatoes_peppers_and_aubergines',
  'legumes': 'beans_and_pulses',
  'citrus': 'fruit',
  'tropical_fruit': 'fruit',
  'stone_fruit': 'fruit',
  'berries': 'fruit',
  'red_meat': 'red_meat',
  'poultry': 'poultry',
  'seafood': 'fish_and_seafood',
  'eggs': 'eggs',
  'dairy': 'dairy',
  'grains': 'grains',
  'pasta_rice': 'pasta_and_rice',
  'bread': 'bread',
  'oils_fats': 'oils_and_fats',
  'herbs_fresh': 'fresh_herbs',
  'herbs_dried': 'dried_herbs',
  'spices': 'spices',
  'condiments': 'sauces_and_condiments',
};

const List<int> _fixtureVersions = <int>[1, 2, 3, 4, 5];

Future<File> _fixtureFile(int version) async {
  final directory = await Directory.systemTemp.createTemp('glean-groups-up-');
  addTearDown(() => directory.delete(recursive: true));
  final file = File('${directory.path}/glean.sqlite');
  final raw = sqlite3.open(file.path);
  raw.execute(
    File('test/data/fixtures/schema_v$version.sql').readAsStringSync(),
  );
  raw.close();
  return file;
}

Future<void> _open(File file) async {
  final db = GleanDatabase(NativeDatabase(file));
  await db.customSelect('SELECT 1').get();
  await db.close();
}

List<String> _columns(Database d, String table) => <String>[
  for (final Row c in d.select('PRAGMA table_info("$table")'))
    c['name'] as String,
];

List<List<Object?>> _rows(
  Database d,
  String table,
  List<String> columns,
) => <List<Object?>>[
  for (final Row r in d.select(
    'SELECT ${columns.map((c) => '"$c"').join(', ')} FROM "$table" ORDER BY rowid',
  ))
    r.values,
];

Map<String, Object?> _one(Database d, String sql) => d.select(sql).single;

void main() {
  for (final int version in _fixtureVersions) {
    test('a version $version file upgrades with every pantry, plan, shopping '
        'and recipe row intact and every ingredient on its group', () async {
      final File file = await _fixtureFile(version);
      final old = sqlite3.open(file.path);
      final tables = <String>[
        for (final Row t in old.select(
          "SELECT name FROM sqlite_master WHERE type = 'table' "
          "AND name NOT LIKE 'sqlite_%'",
        ))
          t['name'] as String,
      ];
      const rewritten = <String>{'ingredients', 'ingredient_categories'};
      final oldColumns = <String, List<String>>{
        for (final String t in tables) t: _columns(old, t),
      };
      final before = <String, List<List<Object?>>>{
        for (final String t in tables)
          if (!rewritten.contains(t)) t: _rows(old, t, oldColumns[t]!),
      };
      final oldIngredients = <Map<String, Object?>>[
        for (final Row r in old.select('SELECT * FROM ingredients ORDER BY id'))
          Map<String, Object?>.of(r),
      ];
      final int oldPantryCount =
          _one(old, 'SELECT count(*) AS n FROM pantry_items')['n']! as int;
      old.close();
      expect(oldIngredients.length, greaterThanOrEqualTo(11));
      expect(oldPantryCount, greaterThanOrEqualTo(1));

      await _open(file);

      final upgraded = sqlite3.open(file.path);
      addTearDown(upgraded.close);
      expect(upgraded.select('PRAGMA user_version').single.values.single, 6);
      for (final String t in before.keys) {
        expect(
          _rows(upgraded, t, oldColumns[t]!).length,
          before[t]!.length,
          reason: '$t keeps every row',
        );
      }
      for (final String t in before.keys.where(
        (String t) =>
            !<String>{'ingredient_overrides', 'catalogue_items'}.contains(t),
      )) {
        expect(
          _rows(upgraded, t, oldColumns[t]!),
          before[t],
          reason: 'every row of $t keeps its old column values',
        );
      }
      expect(upgraded.select('PRAGMA foreign_key_check'), isEmpty);
      final String snapshot = File(
        'test/data/fixtures/schema_v6_snapshot.sql',
      ).readAsStringSync();
      expect(
        snapshot,
        contains(
          '${_one(upgraded, "SELECT sql AS s FROM sqlite_master WHERE name = 'ingredients'")['s']};',
        ),
        reason: 'the rebuilt table is the one a fresh install gets',
      );

      final newIngredients = <int, Map<String, Object?>>{
        for (final Row r in upgraded.select('SELECT * FROM ingredients'))
          r['id'] as int: Map<String, Object?>.of(r),
      };
      expect(newIngredients.length, oldIngredients.length);
      for (final old in oldIngredients) {
        final Map<String, Object?> now = newIngredients[old['id']]!;
        expect(now['canonical_name'], old['canonical_name']);
        expect(now['api_name'], old['api_name']);
        expect(now['canonical_unit'], old['canonical_unit']);
        expect(now['is_staple'], old['is_staple']);
        expect(
          now['group_id'],
          _groupOfOldCategory[old['category']] ?? 'other',
          reason: '${old['canonical_name']} (${old['category']})',
        );
        expect(
          now['form'],
          isNull,
          reason: 'form is never defaulted: ${old['canonical_name']}',
        );
      }
      expect(
        _columns(upgraded, 'ingredients'),
        containsAll(<String>['group_id', 'catalogue_item_id', 'form']),
      );
      expect(
        _columns(upgraded, 'ingredients'),
        isNot(anyOf(contains('category'), contains('api_ingredient_id'))),
      );
      expect(
        upgraded
            .select(
              "SELECT name FROM sqlite_master WHERE name = 'ingredient_categories'",
            )
            .toList(),
        isEmpty,
      );
    });
  }

  group('from the version 5 file, which holds a row in every kind of category', () {
    late File file;
    setUp(() async {
      file = await _fixtureFile(5);
      await _open(file);
    });

    Database openRaw() {
      final raw = sqlite3.open(file.path);
      addTearDown(raw.close);
      return raw;
    }

    String? groupOf(Database d, String name) =>
        _one(
              d,
              "SELECT group_id AS g FROM ingredients WHERE canonical_name = '$name'",
            )['g']
            as String?;

    test('the renamed categories land on their renamed groups', () {
      final raw = openRaw();
      expect(
        groupOf(raw, 'cherry tomatoes'),
        'tomatoes_peppers_and_aubergines',
      );
      expect(groupOf(raw, 'tomatoes'), 'tomatoes_peppers_and_aubergines');
      expect(groupOf(raw, 'garlic'), 'onions_and_garlic');
      expect(groupOf(raw, 'broccoli'), 'cabbage_and_broccoli');
      expect(groupOf(raw, 'olive oil'), 'oils_and_fats');
    });

    test('the four fruit categories merge into Fruit', () {
      final raw = openRaw();
      expect(groupOf(raw, 'lemon'), 'fruit');
      expect(groupOf(raw, 'blueberries'), 'fruit');
    });

    test('an unknown category and a null one both become Other, and no row is '
        'dropped', () {
      final raw = openRaw();
      expect(groupOf(raw, 'ancient grains'), 'other');
      expect(groupOf(raw, 'saffron threads'), 'other');
      expect(_one(raw, 'SELECT count(*) AS n FROM ingredients')['n'], 19);
    });

    test('ingredients the synced catalogue names are linked to their item', () {
      final raw = openRaw();
      Object? itemOf(String name) => _one(
        raw,
        "SELECT catalogue_item_id AS c FROM ingredients WHERE canonical_name = '$name'",
      )['c'];
      expect(itemOf('onion'), 'onion');
      expect(itemOf('ginger'), 'ginger');
      expect(itemOf('tomatoes'), isNull);
      expect(itemOf('saffron threads'), isNull);
    });

    test('a store section chosen for a linkable ingredient moves into its '
        'override beside the override\'s other changes', () {
      final raw = openRaw();
      expect(
        _one(
          raw,
          "SELECT section, unopened_shelf_life_days AS days FROM ingredient_overrides WHERE item_id = 'ginger'",
        ).values,
        <Object?>['Frozen', 30],
      );
      expect(
        _one(
          raw,
          "SELECT store_section AS s FROM ingredients WHERE canonical_name = 'ginger'",
        )['s'],
        isNull,
      );
      expect(
        _one(
          raw,
          "SELECT tracking_mode AS m FROM ingredient_overrides WHERE item_id = 'onion'",
        )['m'],
        'presence',
        reason: 'an override with no section is left as it was',
      );
    });

    test('a store section chosen for an unlinkable ingredient stays where it '
        'is, and still places its shopping row', () async {
      final raw = openRaw();
      expect(
        _one(
          raw,
          "SELECT store_section AS s FROM ingredients WHERE canonical_name = 'black pepper'",
        )['s'],
        'baking',
      );
      expect(
        _one(
          raw,
          "SELECT store_section AS s FROM ingredients WHERE canonical_name = 'saffron threads'",
        )['s'],
        'baking',
      );
      final db = GleanDatabase(NativeDatabase(file));
      addTearDown(db.close);
      final rows = await ShoppingRepository(
        db,
        IngredientsRepository(db),
      ).watchAll('reopen-user').first;
      expect({
        for (final r in rows) r.name: r.section,
      }, containsPair('black pepper', StoreSection.baking));
      expect({
        for (final r in rows) r.name: r.section,
      }, containsPair('saffron threads', StoreSection.baking));
    });

    test(
      'a linked ingredient\'s moved choice still places its shopping row',
      () async {
        final db = GleanDatabase(NativeDatabase(file));
        addTearDown(db.close);
        final rows = await ShoppingRepository(
          db,
          IngredientsRepository(db),
        ).watchAll('reopen-user').first;
        expect(
          rows.firstWhere((r) => r.name == 'ginger').section,
          StoreSection.frozen,
        );
      },
    );

    test('unlinked ingredients keep working: the pantry shows them under their '
        'old food group and takes more of them', () async {
      final db = GleanDatabase(NativeDatabase(file));
      addTearDown(db.close);
      final pantry = PantryRepository(db, IngredientsRepository(db));
      final items = {
        for (final i in await pantry.getAll('reopen-user')) i.canonicalName: i,
      };
      expect(items['tomatoes']!.foodGroup, 'vegetables');
      expect(items['lemon']!.foodGroup, 'fruit');
      expect(items['saffron threads']!.foodGroup, 'other');
      expect(items['ancient grains']!.foodGroup, 'other');
      await pantry.addItem(
        userId: 'reopen-user',
        name: 'tomatoes',
        quantity: 100,
        unit: 'g',
        groupId: null,
      );
      expect(
        (await pantry.getAll(
          'reopen-user',
        )).firstWhere((i) => i.canonicalName == 'tomatoes').quantity,
        500,
      );
    });

    test('opening the upgraded file again changes nothing', () async {
      Map<String, List<List<Object?>>> snapshot() {
        final raw = sqlite3.open(file.path);
        try {
          return <String, List<List<Object?>>>{
            for (final Row t in raw.select(
              "SELECT name FROM sqlite_master WHERE type = 'table' "
              "AND name NOT LIKE 'sqlite_%'",
            ))
              t['name'] as String: _rows(
                raw,
                t['name'] as String,
                _columns(raw, t['name'] as String),
              ),
          };
        } finally {
          raw.close();
        }
      }

      final first = snapshot();
      await _open(file);
      expect(snapshot(), first);
    });

    test('running the upgrade step a second time over upgraded data is '
        'harmless', () async {
      Map<String, List<List<Object?>>> snapshot() {
        final raw = sqlite3.open(file.path);
        try {
          return <String, List<List<Object?>>>{
            for (final Row t in raw.select(
              "SELECT name FROM sqlite_master WHERE type = 'table' "
              "AND name NOT LIKE 'sqlite_%'",
            ))
              t['name'] as String: _rows(
                raw,
                t['name'] as String,
                _columns(raw, t['name'] as String),
              ),
          };
        } finally {
          raw.close();
        }
      }

      final first = snapshot();
      final raw = sqlite3.open(file.path);
      raw.execute('PRAGMA user_version = 5');
      raw.close();
      await _open(file);
      expect(snapshot(), first);
    });
  });

  test('an upgrade that fails part-way leaves the version 5 file exactly as '
      'it was', () async {
    final File file = await _fixtureFile(5);
    final raw = sqlite3.open(file.path);
    // Linking moves ginger's section into its override: make that write fail after the table has been rebuilt.
    raw.execute(
      'CREATE TRIGGER fail_override_update BEFORE UPDATE ON ingredient_overrides '
      "BEGIN SELECT RAISE(ABORT, 'boom'); END",
    );
    final tables = <String>[
      for (final Row t in raw.select(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%'",
      ))
        t['name'] as String,
    ];
    final before = <String, List<List<Object?>>>{
      for (final String t in tables) t: _rows(raw, t, _columns(raw, t)),
    };
    final schemaBefore = raw
        .select('SELECT sql FROM sqlite_master ORDER BY name')
        .map((Row r) => r['sql'])
        .toList();
    raw.close();

    final db = GleanDatabase(NativeDatabase(file));
    await expectLater(db.customSelect('SELECT 1').get(), throwsA(anything));
    await db.close();

    final after = sqlite3.open(file.path);
    addTearDown(after.close);
    expect(after.select('PRAGMA user_version').single.values.single, 5);
    expect(
      after
          .select('SELECT sql FROM sqlite_master ORDER BY name')
          .map((Row r) => r['sql'])
          .toList(),
      schemaBefore,
    );
    for (final String t in tables) {
      expect(_rows(after, t, _columns(after, t)), before[t], reason: t);
    }
  });
}
