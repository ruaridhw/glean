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
      expect(onDisk.select('PRAGMA user_version').single.values.single, 2);
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
        File('${liveFile.path}.restore-staging').existsSync(),
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
      File('${liveFile.path}.restore-staging').existsSync(),
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
}
