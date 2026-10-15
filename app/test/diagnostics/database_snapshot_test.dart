import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/diagnostics/database_snapshot.dart';
import 'package:sqlite3/sqlite3.dart' as sqlite;

int _count(sqlite.Database db, String table) =>
    db.select('SELECT COUNT(*) AS n FROM $table').single['n'] as int;

void main() {
  late Directory dir;
  late GleanDatabase live;

  setUp(() async {
    dir = Directory.systemTemp.createTempSync('glean_snapshot_test');
    live = GleanDatabase(NativeDatabase(File('${dir.path}/live.sqlite')));
    await live.customStatement(
      "INSERT INTO user_config (id, meals_per_week) VALUES ('user-1', 4)",
    );
  });

  tearDown(() async {
    await live.close();
    dir.deleteSync(recursive: true);
  });

  test(
    'a snapshot opens with sqlite3 and its row counts match the live database',
    () async {
      final File snapshot = await snapshotDatabase(live, dir);

      final sqlite.Database copy = sqlite.sqlite3.open(snapshot.path);
      addTearDown(copy.dispose);
      expect(copy.select('PRAGMA integrity_check').single.values, <Object?>[
        'ok',
      ]);
      for (final String table in <String>[
        'ingredient_categories',
        'ingredients',
        'user_config',
      ]) {
        final int liveCount =
            (await live
                    .customSelect('SELECT COUNT(*) AS n FROM $table')
                    .getSingle())
                .read<int>('n');
        expect(_count(copy, table), liveCount, reason: table);
      }
      expect(_count(copy, 'user_config'), 1);
      expect(copy.select('PRAGMA user_version').single.values.single, 2);
    },
  );

  test(
    'taking a snapshot leaves the live database writable and unchanged',
    () async {
      await snapshotDatabase(live, dir);

      await live.customStatement(
        "INSERT INTO user_config (id) VALUES ('user-2')",
      );
      final int count =
          (await live
                  .customSelect('SELECT COUNT(*) AS n FROM user_config')
                  .getSingle())
              .read<int>('n');
      expect(count, 2);
    },
  );

  test('a second snapshot replaces the first rather than failing', () async {
    await snapshotDatabase(live, dir);
    await live.customStatement(
      "INSERT INTO user_config (id) VALUES ('user-2')",
    );

    final File second = await snapshotDatabase(live, dir);

    final sqlite.Database copy = sqlite.sqlite3.open(second.path);
    addTearDown(copy.dispose);
    expect(_count(copy, 'user_config'), 2);
  });
}
