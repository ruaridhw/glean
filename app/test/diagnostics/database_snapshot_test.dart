import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth.dart';
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
      addTearDown(copy.close);
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
    addTearDown(copy.close);
    expect(_count(copy, 'user_config'), 2);
  });

  test(
    'a signed-in session leaves no token or session value anywhere in the backup file',
    () async {
      FlutterSecureStorage.setMockInitialValues(<String, String>{});
      const String access = 'opaque-access-9f3a1c';
      const String refresh = 'opaque-refresh-77be20';
      const String idToken = 'opaque-id-c04d58';
      await TokenStorage().saveTokens(
        CognitoTokens(
          accessToken: access,
          refreshToken: refresh,
          idToken: idToken,
          userSub: 'user-1',
          email: 'owner@example.com',
          expiresAt: DateTime.utc(2026, 10, 15, 12),
        ),
      );

      final File snapshot = await snapshotDatabase(live, dir);

      final String raw = String.fromCharCodes(snapshot.readAsBytesSync());
      for (final String secret in <String>[
        access,
        refresh,
        idToken,
        'owner@example.com',
      ]) {
        expect(raw, isNot(contains(secret)));
      }
      final sqlite.Database copy = sqlite.sqlite3.open(snapshot.path);
      addTearDown(copy.close);
      final Set<String> tables = copy
          .select("SELECT name FROM sqlite_master WHERE type = 'table'")
          .map((r) => r['name'] as String)
          .toSet();
      expect(
        tables.where(
          (t) => RegExp('token|session|auth|secret').hasMatch(t),
        ),
        isEmpty,
      );
    },
  );
}
