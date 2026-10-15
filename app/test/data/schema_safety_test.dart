// Guards for the user's on-device data, which is the only copy (local SQLite
// is the sole source of truth; nothing syncs to the server).
//
// - A schema change must come with a `schemaVersion` bump and an `onUpgrade`
//   step, or existing installs open a database whose tables no longer match.
//   The snapshot below fails on any table/index change until both are done.
// - A build must never open a database written by a newer build: the
//   `onUpgrade` steps would then be skipped on the way back down and re-run
//   (and fail) on the way back up, leaving the app unable to open its data.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:sqlite3/sqlite3.dart';

Future<String> _schemaOf(GleanDatabase db) async {
  final rows = await db
      .customSelect(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type, name",
      )
      .get();
  return '${rows.map((r) => '${r.read<String>('sql')};').join('\n')}\n';
}

void main() {
  test('the schema matches the snapshot for its schemaVersion, so a table '
      'change cannot ship without a migration', () async {
    final db = GleanDatabase(NativeDatabase.memory());
    addTearDown(db.close);
    final File snapshot = File(
      'test/data/fixtures/schema_v${db.schemaVersion}_snapshot.sql',
    );

    expect(
      snapshot.existsSync(),
      isTrue,
      reason:
          'schemaVersion is ${db.schemaVersion} but ${snapshot.path} is '
          'missing. Add it, an onUpgrade step from the previous version, and '
          'a frozen schema_v${db.schemaVersion - 1}.sql fixture with a '
          'reopen test (see database_reopen_test.dart).',
    );
    expect(
      await _schemaOf(db),
      snapshot.readAsStringSync(),
      reason:
          'The tables changed without a schemaVersion bump. Bump '
          'schemaVersion, add the onUpgrade step, and snapshot the new '
          'schema; never edit this snapshot in place.',
    );
    for (var v = 1; v < db.schemaVersion; v++) {
      expect(
        File('test/data/fixtures/schema_v$v.sql').existsSync(),
        isTrue,
        reason: 'Every earlier version needs a frozen fixture to migrate from.',
      );
    }
  });

  test('refuses to open a database written by a newer build and leaves its '
      'data untouched', () async {
    final directory = await Directory.systemTemp.createTemp('glean-newer-');
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/glean.sqlite');

    final current = GleanDatabase(NativeDatabase(file));
    final recipes = RecipesRepository(current, IngredientsRepository(current));
    await recipes.save(
      userId: 'u',
      externalId: 'rec_keep',
      title: 'Kept dinner',
      ingredients: const [],
    );
    await current.close();

    final int newer = current.schemaVersion + 1;
    final raw = sqlite3.open(file.path);
    raw.execute('PRAGMA user_version = $newer');
    raw.close();

    final older = GleanDatabase(NativeDatabase(file));
    await expectLater(older.select(older.recipes).get(), throwsA(anything));
    await older.close();

    final check = sqlite3.open(file.path);
    addTearDown(check.close);
    expect(check.select('PRAGMA user_version').single.values.single, newer);
    expect(
      check.select("SELECT title FROM recipes WHERE external_id = 'rec_keep'"),
      hasLength(1),
    );
  });
}
