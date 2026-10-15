import 'dart:io';

import 'package:drift/drift.dart' show Variable;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/diagnostics/diagnostics.dart';

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
}
