// The upgrade that adds the household profile table is additive: every frozen older database file must
// open on the current schema with its rows untouched and gain an empty `household_profiles`. A file at a
// version whose own migration lands in another branch (v7) is covered too, because it opens here either way.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:sqlite3/sqlite3.dart';

Future<File> _fixtureFile(int version) async {
  final directory = await Directory.systemTemp.createTemp('glean-profile-');
  addTearDown(() => directory.delete(recursive: true));
  final file = File('${directory.path}/glean.sqlite');
  final raw = sqlite3.open(file.path);
  raw.execute(
    File('test/data/fixtures/schema_v$version.sql').readAsStringSync(),
  );
  raw.close();
  return file;
}

/// Every table and its rows as the frozen file holds them, so the upgrade can be compared row by row.
Map<String, List<List<Object?>>> _dump(Database raw) {
  final List<String> tables = <String>[
    for (final Row table in raw.select(
      "SELECT name FROM sqlite_master WHERE type = 'table' "
      "AND name NOT LIKE 'sqlite_%'",
    ))
      table['name'] as String,
  ];
  return <String, List<List<Object?>>>{
    for (final String table in tables)
      table: <List<Object?>>[
        for (final Row row in raw.select(
          'SELECT * FROM "$table" ORDER BY rowid',
        ))
          row.values,
      ],
  };
}

void main() {
  for (final int fixtureVersion in <int>[6, 7]) {
    test('a version $fixtureVersion file upgrades to the current schema with '
        'every row intact and gains an empty household_profiles', () async {
      final File file = await _fixtureFile(fixtureVersion);

      final Database before = sqlite3.open(file.path);
      expect(
        before.select('PRAGMA user_version').single.values.single,
        fixtureVersion,
      );
      final Map<String, List<List<Object?>>> rowsBefore = _dump(before);
      before.close();
      // The fixture carries the owner's own data, not just an empty schema.
      expect(rowsBefore['user_config'], hasLength(1));
      expect(rowsBefore['pantry_items'], hasLength(1));
      expect(rowsBefore['meal_plan_entries'], hasLength(1));
      expect(rowsBefore['recipes'], hasLength(1));

      final GleanDatabase db = GleanDatabase(NativeDatabase(file));
      await db.customSelect('SELECT 1').get();
      expect(
        await UserConfigRepository(
          db,
        ).watchGroupShoppingBySection('reopen-user').first,
        isTrue,
      );
      // The new table is there, empty, and writable.
      final int currentVersion = db.schemaVersion;
      expect(await db.select(db.householdProfiles).get(), isEmpty);
      await db
          .into(db.householdProfiles)
          .insert(
            HouseholdProfilesCompanion.insert(
              userId: 'reopen-user',
              profileJson: '{"version":1}',
              updatedAt: '2026-10-24T10:00:00.000',
            ),
          );
      await db.close();

      final Database after = sqlite3.open(file.path);
      addTearDown(after.close);
      expect(
        after.select('PRAGMA user_version').single.values.single,
        currentVersion,
      );
      final Map<String, List<List<Object?>>> rowsAfter = _dump(after);
      for (final String table in rowsBefore.keys) {
        expect(
          rowsAfter[table],
          rowsBefore[table],
          reason: 'every row of $table keeps its values through the upgrade',
        );
      }
      expect(
        after
            .select('SELECT count(*) FROM household_profiles')
            .single
            .values
            .single,
        1,
      );
    });
  }

  test('the profile row survives a reopen, so an upgrade never touches it '
      'a second time', () async {
    final File file = await _fixtureFile(6);
    var db = GleanDatabase(NativeDatabase(file));
    await db
        .into(db.householdProfiles)
        .insert(
          HouseholdProfilesCompanion.insert(
            userId: 'reopen-user',
            profileJson: '{"version":1}',
            updatedAt: '2026-10-24T10:00:00.000',
          ),
        );
    await db.close();

    db = GleanDatabase(NativeDatabase(file));
    addTearDown(db.close);
    expect(await db.select(db.householdProfiles).get(), hasLength(1));
  });
}
