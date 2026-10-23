import 'dart:io';

import 'package:drift/drift.dart' show Variable;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:sqlite3/sqlite3.dart' as sqlite;

Future<int> _mealsPerWeek(GleanDatabase db, String user) async =>
    (await db
            .customSelect(
              'SELECT meals_per_week AS n FROM user_config WHERE id = ?',
              variables: <Variable>[Variable<String>(user)],
            )
            .getSingle())
        .read<int>('n');

void main() {
  late Directory dir;
  late File liveFile;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_restore_test');
    liveFile = File('${dir.path}/glean.sqlite');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  List<String> stagingLeftovers() => dir
      .listSync()
      .map((e) => e.path.split('/').last)
      .where((n) => n.contains('restore-staging'))
      .toList();

  GleanDatabase open(File file) => GleanDatabase(NativeDatabase(file));

  test(
    'a backup exported from one install restores onto a fresh install of the same version',
    () async {
      final GleanDatabase before = open(File('${dir.path}/before.sqlite'));
      await before.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('user-1', 4)",
      );
      final File backup = await snapshotDatabase(before, dir);
      await before.close();
      final GleanDatabase freshInstall = open(liveFile);
      await freshInstall.customStatement('SELECT 1');

      await restoreDatabase(
        backup: backup,
        live: freshInstall,
        liveFile: liveFile,
      );

      final GleanDatabase restored = open(liveFile);
      addTearDown(restored.close);
      expect(await _mealsPerWeek(restored, 'user-1'), 4);
    },
  );

  test('a backup carries the household ratings a restore must bring back', () async {
    final GleanDatabase before = open(File('${dir.path}/before.sqlite'));
    await before.customStatement(
      'INSERT INTO meal_plan_entries (user_id, recipe_title, planned_date, cooked_at, servings) '
      "VALUES ('user-1', 'Curry', '2026-10-05', '2026-10-06T18:30:00.000', 2)",
    );
    await before.customStatement(
      'INSERT INTO meal_ratings (user_id, meal_plan_entry_id, rating, note, created_at) '
      "VALUES ('user-1', 1, 'down', 'too sweet', '2026-10-06T19:00:00.000Z')",
    );
    final File backup = await snapshotDatabase(before, dir);
    await before.close();
    final GleanDatabase freshInstall = open(liveFile);
    await freshInstall.customStatement('SELECT 1');

    await restoreDatabase(
      backup: backup,
      live: freshInstall,
      liveFile: liveFile,
    );

    final GleanDatabase restored = open(liveFile);
    addTearDown(restored.close);
    final row = await restored
        .customSelect(
          'SELECT rating, note FROM meal_ratings WHERE user_id = ?',
          variables: <Variable>[const Variable<String>('user-1')],
        )
        .getSingle();
    expect(row.read<String>('rating'), 'down');
    expect(row.read<String>('note'), 'too sweet');
  });

  /// A database file as the oldest shipped build wrote it (frozen schema_v1 fixture).
  File versionOneBackup() {
    final File file = File('${dir.path}/v1-backup.sqlite');
    final sqlite.Database raw = sqlite.sqlite3.open(file.path);
    raw.execute(File('test/data/fixtures/schema_v1.sql').readAsStringSync());
    raw.close();
    return file;
  }

  test(
    'a backup from an older schema version is migrated forward as part of the restore',
    () async {
      final GleanDatabase freshInstall = open(liveFile);
      await freshInstall.customStatement('SELECT 1');

      await restoreDatabase(
        backup: versionOneBackup(),
        live: freshInstall,
        liveFile: liveFile,
      );

      final sqlite.Database onDisk = sqlite.sqlite3.open(liveFile.path);
      addTearDown(onDisk.close);
      expect(
        onDisk.select('PRAGMA user_version').single.values.single,
        freshInstall.schemaVersion,
      );
      expect(
        onDisk
            .select('SELECT title FROM recipes')
            .map((r) => r['title'])
            .toList(),
        <Object?>['Persisted dinner'],
        reason: "the old build's recipes survive the migration",
      );
    },
  );

  File backupWithSchemaVersion(int version) {
    final File file = File('${dir.path}/v$version-backup.sqlite');
    final sqlite.Database raw = sqlite.sqlite3.open(file.path);
    raw.execute('CREATE TABLE from_the_future (id INTEGER PRIMARY KEY)');
    raw.execute('PRAGMA user_version = $version');
    raw.close();
    return file;
  }

  Future<GleanDatabase> liveWithUserConfig() async {
    final GleanDatabase live = open(liveFile);
    await live.customStatement(
      "INSERT INTO user_config (id, meals_per_week) VALUES ('mine', 6)",
    );
    return live;
  }

  test(
    'a backup from a newer schema version is refused and the live database is left untouched',
    () async {
      final GleanDatabase live = await liveWithUserConfig();
      final GleanDatabase peek = open(File('${dir.path}/peek.sqlite'));
      addTearDown(peek.close);
      final int appVersion = peek.schemaVersion;

      await expectLater(
        restoreDatabase(
          backup: backupWithSchemaVersion(appVersion + 1),
          live: live,
          liveFile: liveFile,
        ),
        throwsA(
          isA<BackupTooNewException>().having(
            (e) => e.toString(),
            'message',
            allOf(contains('newer'), contains('Update')),
          ),
        ),
      );

      expect(
        await _mealsPerWeek(live, 'mine'),
        6,
        reason: 'the live database must still be open and usable',
      );
      await live.close();
      final GleanDatabase reopened = open(liveFile);
      addTearDown(reopened.close);
      expect(await _mealsPerWeek(reopened, 'mine'), 6);
      expect(
        dir.listSync().map((e) => e.path.split('/').last).toSet(),
        containsAll(<String>['glean.sqlite']),
      );
      expect(
        stagingLeftovers().isNotEmpty,
        isFalse,
        reason: 'a refused backup leaves no staging file behind',
      );
    },
  );

  Future<void> expectLiveUntouchedAfterRefusal(File backup) async {
    final GleanDatabase live = await liveWithUserConfig();

    await expectLater(
      restoreDatabase(backup: backup, live: live, liveFile: liveFile),
      throwsA(isA<BackupInvalidException>()),
    );

    expect(await _mealsPerWeek(live, 'mine'), 6);
    await live.close();
    final GleanDatabase reopened = open(liveFile);
    addTearDown(reopened.close);
    expect(await _mealsPerWeek(reopened, 'mine'), 6);
    expect(
      stagingLeftovers().isNotEmpty,
      isFalse,
      reason: 'a refused backup leaves no staging file behind',
    );
  }

  test(
    'a download cut off half-way is refused and the live database is left untouched',
    () async {
      final GleanDatabase source = open(File('${dir.path}/source.sqlite'));
      await source.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('theirs', 3)",
      );
      final File whole = await snapshotDatabase(source, dir);
      await source.close();
      final List<int> bytes = whole.readAsBytesSync();
      final File truncated = File('${dir.path}/truncated.sqlite')
        ..writeAsBytesSync(bytes.sublist(0, bytes.length ~/ 2));

      await expectLiveUntouchedAfterRefusal(truncated);
    },
  );

  test(
    'a file that is not a database is refused and the live database is left untouched',
    () async {
      final File junk = File('${dir.path}/junk.sqlite')
        ..writeAsBytesSync(List<int>.filled(4096, 7));

      await expectLiveUntouchedAfterRefusal(junk);
    },
  );

  test(
    'rows still in the live write-ahead log never leak into the restored database, and the previous database is kept',
    () async {
      final GleanDatabase source = open(File('${dir.path}/source.sqlite'));
      await source.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('theirs', 3)",
      );
      final File backup = await snapshotDatabase(source, dir);
      await source.close();
      final GleanDatabase live = open(liveFile);
      await live.customStatement('PRAGMA journal_mode = WAL');
      await live.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('mine', 6)",
      );
      expect(
        File('${liveFile.path}-wal').lengthSync(),
        greaterThan(0),
        reason: 'precondition: the row is only in the write-ahead log',
      );

      await restoreDatabase(backup: backup, live: live, liveFile: liveFile);

      final GleanDatabase restored = open(liveFile);
      addTearDown(restored.close);
      expect(await _mealsPerWeek(restored, 'theirs'), 3);
      final rows = await restored
          .customSelect('SELECT id FROM user_config')
          .get();
      expect(rows.map((r) => r.read<String>('id')), <String>['theirs']);
      final GleanDatabase previous = open(File('${liveFile.path}.pre-restore'));
      addTearDown(previous.close);
      expect(await _mealsPerWeek(previous, 'mine'), 6);
    },
  );

  File unrelatedDatabase(int version) {
    final File file = File('${dir.path}/unrelated-v$version.sqlite');
    final sqlite.Database raw = sqlite.sqlite3.open(file.path);
    raw.execute('CREATE TABLE unrelated (id INTEGER PRIMARY KEY)');
    raw.execute('PRAGMA user_version = $version');
    raw.close();
    return file;
  }

  test(
    'a valid SQLite database that is not a Glean database is refused at the current and an older version, leaving live untouched',
    () async {
      final GleanDatabase probe = open(File('${dir.path}/probe.sqlite'));
      addTearDown(probe.close);
      for (final int version in <int>[probe.schemaVersion, 1]) {
        await expectLiveUntouchedAfterRefusal(unrelatedDatabase(version));
        File(liveFile.path).deleteSync();
      }
    },
  );

  test(
    'an unversioned database is refused rather than being created as a fresh install',
    () async {
      await expectLiveUntouchedAfterRefusal(unrelatedDatabase(0));
    },
  );

  test(
    'a prepared backup missing a required column is refused and live stays untouched',
    () async {
      final GleanDatabase source = open(File('${dir.path}/source.sqlite'));
      await source.customStatement('SELECT 1');
      final File snapshot = await snapshotDatabase(source, dir);
      await source.close();
      final sqlite.Database raw = sqlite.sqlite3.open(snapshot.path);
      raw.execute('ALTER TABLE user_config DROP COLUMN meals_per_week');
      raw.close();

      await expectLiveUntouchedAfterRefusal(snapshot);
    },
  );

  test(
    'a failure after the live database is closed is reported as interrupted and the previous database file is intact',
    () async {
      final GleanDatabase source = open(File('${dir.path}/source.sqlite'));
      await source.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('theirs', 3)",
      );
      final File backup = await snapshotDatabase(source, dir);
      await source.close();
      final GleanDatabase live = await liveWithUserConfig();
      // The kept copy of the previous database cannot be written: a real filesystem failure that only shows
      // up once the live connection is already closed.
      Directory('${liveFile.path}.pre-restore').createSync();

      await expectLater(
        restoreDatabase(backup: backup, live: live, liveFile: liveFile),
        throwsA(isA<RestoreInterruptedException>()),
      );

      final GleanDatabase reopened = open(liveFile);
      addTearDown(reopened.close);
      expect(await _mealsPerWeek(reopened, 'mine'), 6);
      expect(stagingLeftovers().isNotEmpty, isFalse);
    },
  );

  /// What a process killed mid-migration leaves beside the live file: a staging database whose write-ahead log
  /// still holds uncheckpointed pages from the first backup.
  Future<void> abandonStagingWithPendingWal(String stagingName) async {
    final File stagedByFirst = File('${liveFile.path}.$stagingName');
    final GleanDatabase first = open(File('${dir.path}/first.sqlite'));
    await first.customStatement(
      "INSERT INTO user_config (id, meals_per_week) VALUES ('first', 1)",
    );
    final File firstBackup = await snapshotDatabase(first, dir);
    await first.close();
    firstBackup.copySync(stagedByFirst.path);
    final sqlite.Database raw = sqlite.sqlite3.open(stagedByFirst.path);
    raw.execute('PRAGMA journal_mode = WAL');
    raw.execute('PRAGMA wal_autocheckpoint = 0');
    raw.execute(
      "INSERT INTO user_config (id, meals_per_week) VALUES ('first-wal', 2)",
    );
    // Copy the files while the connection is still open, as a kill would leave them, then let go.
    final Directory crashed = Directory('${dir.path}/crashed')..createSync();
    for (final String suffix in <String>['', '-wal', '-shm']) {
      final File f = File('${stagedByFirst.path}$suffix');
      if (f.existsSync()) f.copySync('${crashed.path}/$stagingName$suffix');
    }
    raw.close();
    for (final String suffix in <String>['', '-wal', '-shm']) {
      final File f = File('${stagedByFirst.path}$suffix');
      if (f.existsSync()) f.deleteSync();
      final File c = File('${crashed.path}/$stagingName$suffix');
      if (c.existsSync()) c.copySync(f.path);
    }
    expect(
      File('${stagedByFirst.path}-wal').lengthSync(),
      greaterThan(0),
      reason: 'precondition: an abandoned write-ahead log is on disk',
    );
  }

  test(
    'a retry after a migration was killed restores wholly from the newly chosen backup, never mixing in the abandoned one',
    () async {
      await abandonStagingWithPendingWal('restore-staging');
      final GleanDatabase second = open(File('${dir.path}/second.sqlite'));
      await second.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('second', 3)",
      );
      final File secondBackup = await snapshotDatabase(second, dir);
      await second.close();
      final GleanDatabase live = await liveWithUserConfig();

      await restoreDatabase(
        backup: secondBackup,
        live: live,
        liveFile: liveFile,
      );

      final GleanDatabase restored = open(liveFile);
      addTearDown(restored.close);
      final rows = await restored
          .customSelect('SELECT id FROM user_config ORDER BY id')
          .get();
      expect(rows.map((r) => r.read<String>('id')), <String>['second']);
    },
  );

  test(
    'abandoned staging files from earlier attempts are cleared, and the live database and its files are not touched',
    () async {
      await abandonStagingWithPendingWal('restore-staging-1700000000000000');
      File('${liveFile.path}.restore-staging-ab12').writeAsStringSync('junk');
      final GleanDatabase source = open(File('${dir.path}/source.sqlite'));
      await source.customStatement('SELECT 1');
      final File backup = await snapshotDatabase(source, dir);
      await source.close();
      final GleanDatabase live = await liveWithUserConfig();

      await restoreDatabase(backup: backup, live: live, liveFile: liveFile);

      final List<String> leftovers = dir
          .listSync()
          .map((e) => e.path.split('/').last)
          .where((n) => n.startsWith('glean.sqlite.restore-staging'))
          .toList();
      expect(leftovers, isEmpty);
      expect(File('${liveFile.path}.pre-restore').existsSync(), isTrue);
    },
  );
}
