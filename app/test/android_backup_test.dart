// Android Auto Backup is the only off-phone copy of the user's data (local
// SQLite is the sole source of truth), so it must stay on and must keep the
// database. flutter_secure_storage's README suggests `allowBackup="false"`;
// don't: exclude just its two preference files instead. Their Keystore keys
// never leave the device, so a restored copy can't be decrypted and only
// forces a fresh sign-in. drift_flutter keeps the database under
// `app_flutter/` (backup domain `root`).
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const List<String> _secureStorageFiles = <String>[
  'FlutterSecureStorage.xml',
  'FlutterSecureKeyStorage.xml',
];

String _read(String path) =>
    File('android/app/src/main/$path').readAsStringSync();

void main() {
  final String manifest = _read('AndroidManifest.xml');
  final String application = RegExp(
    r'<application\s[^>]*>',
  ).firstMatch(manifest)![0]!;

  test('backup stays on and both rule sets are wired up', () {
    expect(application, isNot(contains('android:allowBackup="false"')));
    expect(
      application,
      contains('android:dataExtractionRules="@xml/data_extraction_rules"'),
    );
    expect(
      application,
      contains('android:fullBackupContent="@xml/backup_rules"'),
    );
  });

  for (final String rules in <String>[
    'res/xml/data_extraction_rules.xml',
    'res/xml/backup_rules.xml',
  ]) {
    test('$rules keeps the database and leaves out only secure storage', () {
      final String xml = _read(rules);
      final List<RegExpMatch> excludes = RegExp(
        r'<exclude\s+domain="([^"]+)"\s+path="([^"]+)"',
      ).allMatches(xml).toList();
      final int sections = rules.contains('extraction') ? 2 : 1;

      expect(xml, isNot(contains('<include')));
      expect(excludes, hasLength(_secureStorageFiles.length * sections));
      for (final RegExpMatch e in excludes) {
        expect(e[1], 'sharedpref');
        expect(_secureStorageFiles, contains(e[2]));
      }
      if (sections == 2) {
        expect(xml, contains('<cloud-backup>'));
        expect(xml, contains('<device-transfer>'));
      }
    });
  }
}
