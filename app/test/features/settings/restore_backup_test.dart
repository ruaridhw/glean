// Settings' developer-only Restore from backup: lists the user's backups through the API, and replaces the
// phone's database with the chosen one. Everything is real (files, drift, providers) except the HTTP client.
import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:sqlite3/sqlite3.dart' as sqlite;

const Key _versionLabel = Key('settings.versionLabel');
const Key _restoreButton = Key('settings.restoreBackup');

const String _preparedUrl = 'https://bucket.s3.amazonaws.com/prepared';
const String _exportedUrl = 'https://bucket.s3.amazonaws.com/exported';
const String _newerUrl = 'https://bucket.s3.amazonaws.com/newer';

Map<String, Object?> _entry({
  required String id,
  required String url,
  bool prepared = false,
  String? label,
  int? schemaVersion = 2,
}) => <String, Object?>{
  'id': id,
  'created_at': '2026-10-15T12:00:00+00:00',
  'prepared': prepared,
  'label': label,
  'schema_version': schemaVersion,
  'size': 4096,
  'download_url': url,
};

class _Harness {
  _Harness(this.dir) {
    tempRoot = Directory('${dir.path}/tmp')..createSync();
    liveFile = File('${dir.path}/glean.sqlite');
  }

  final Directory dir;
  late final Directory tempRoot;
  late final File liveFile;
  final List<http.Request> requests = <http.Request>[];

  /// Backend behaviour: the list, and the bytes behind each signed URL.
  List<Map<String, Object?>> backups = <Map<String, Object?>>[];
  final Map<String, List<int>> downloads = <String, List<int>>{};
  int listStatus = 200;

  Future<http.Response> _backend(http.Request request) async {
    requests.add(request);
    if (request.url.path == '/dev/backups') {
      return http.Response(
        jsonEncode(<String, Object?>{'backups': backups}),
        listStatus,
      );
    }
    final List<int>? bytes = downloads[request.url.toString()];
    return bytes == null
        ? http.Response('', 404)
        : http.Response.bytes(bytes, 200);
  }

  Widget app() {
    return ProviderScope(
      overrides: [
        gleanDatabaseProvider.overrideWith((ref) {
          final GleanDatabase db = GleanDatabase(NativeDatabase(liveFile));
          ref.onDispose(db.close);
          return db;
        }),
        databaseFileProvider.overrideWithValue(() async => liveFile),
        currentUserIdProvider.overrideWithValue('user-1'),
        diagnosticsTempDirProvider.overrideWithValue(() async => tempRoot),
        apiBaseUrlProvider.overrideWithValue('http://localhost:8000'),
        apiAccessTokenProvider.overrideWithValue(() async => 'test-token'),
        httpClientProvider.overrideWithValue(MockClient(_backend)),
      ],
      child: MaterialApp(theme: gleanLightTheme, home: const SettingsScreen()),
    );
  }
}

Future<void> _waitForContent(WidgetTester tester) async {
  for (var i = 0; i < 40; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 25)),
    );
    await tester.pump(const Duration(milliseconds: 50));
    if (find.byType(SkeletonBox).evaluate().isEmpty) return;
  }
  fail('Settings content never appeared past the loading skeleton.');
}

Future<void> _reveal(WidgetTester tester, Key key) async {
  await tester.scrollUntilVisible(
    find.byKey(key),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _unlockDeveloperMode(WidgetTester tester) async {
  await _reveal(tester, _versionLabel);
  for (var i = 0; i < 7; i++) {
    await tester.tap(find.byKey(_versionLabel));
    await tester.pump();
  }
  await _reveal(tester, _restoreButton);
}

/// Lets real file and database work finish outside the fake-async zone until [text] shows.
Future<void> _until(WidgetTester tester, String text) async {
  for (var i = 0; i < 60 && find.textContaining(text).evaluate().isEmpty; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    await tester.pump();
  }
}

void _settingsWidgetTest(
  String description,
  Future<void> Function(WidgetTester tester) body,
) {
  testWidgets(description, (WidgetTester tester) async {
    try {
      await body(tester);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 1));
    }
  });
}

/// A real database file as the app writes it, holding one `user-1` row with [mealsPerWeek].
Future<List<int>> _backupBytes(
  Directory dir,
  String name, {
  required int mealsPerWeek,
}) async {
  final File file = File('${dir.path}/$name.sqlite');
  final GleanDatabase db = GleanDatabase(NativeDatabase(file));
  await db.customStatement(
    "INSERT INTO user_config (id, meals_per_week) VALUES ('user-1', $mealsPerWeek)",
  );
  await db.close();
  return file.readAsBytesSync();
}

/// A database file claiming a schema version this build does not know.
List<int> _newerBackupBytes(Directory dir) {
  final File file = File('${dir.path}/newer.sqlite');
  final sqlite.Database raw = sqlite.sqlite3.open(file.path);
  raw.execute('CREATE TABLE from_the_future (id INTEGER PRIMARY KEY)');
  raw.execute('PRAGMA user_version = 99');
  raw.close();
  return file.readAsBytesSync();
}

void main() {
  late Directory dir;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('glean_restore_ui_test');
    PackageInfo.setMockInitialValues(
      appName: 'Glean',
      packageName: 'com.ruaridhw.glean',
      version: '1.0.0',
      buildNumber: '1474560',
      buildSignature: '',
    );
  });
  tearDown(() => dir.deleteSync(recursive: true));

  _settingsWidgetTest(
    'restore from backup is hidden until developer mode, then lists prepared backups first and labelled',
    (tester) async {
      final _Harness h = _Harness(dir)
        ..backups = <Map<String, Object?>>[
          _entry(
            id: 'db-exports/user-1/20260101T000000000000Z/',
            url: _preparedUrl,
            prepared: true,
            label: 'ml to presence conversion',
          ),
          _entry(
            id: 'db-exports/user-1/20261015T120000000000Z/',
            url: _exportedUrl,
          ),
        ];
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      expect(find.byKey(_restoreButton), findsNothing);

      await _unlockDeveloperMode(tester);
      await tester.tap(find.byKey(_restoreButton));
      await _until(tester, 'ml to presence conversion');

      expect(find.text('Prepared'), findsOneWidget);
      expect(find.textContaining('ml to presence conversion'), findsOneWidget);
      final double preparedY = tester
          .getTopLeft(
            find.byKey(
              const Key(
                'restore.backup.db-exports/user-1/20260101T000000000000Z/',
              ),
            ),
          )
          .dy;
      final double exportedY = tester
          .getTopLeft(
            find.byKey(
              const Key(
                'restore.backup.db-exports/user-1/20261015T120000000000Z/',
              ),
            ),
          )
          .dy;
      expect(preparedY, lessThan(exportedY));
    },
  );

  Future<int> mealsPerWeekOnDisk(
    WidgetTester tester,
    _Harness h,
  ) async => (await tester.runAsync(() async {
    final GleanDatabase db = GleanDatabase(NativeDatabase(h.liveFile));
    final int n =
        (await db
                .customSelect(
                  "SELECT meals_per_week AS n FROM user_config WHERE id = 'user-1'",
                )
                .getSingle())
            .read<int>('n');
    await db.close();
    return n;
  }))!;

  Future<_Harness> openedWithLiveData(WidgetTester tester) async {
    final _Harness h = _Harness(dir);
    await tester.runAsync(() async {
      final GleanDatabase live = GleanDatabase(NativeDatabase(h.liveFile));
      await live.customStatement(
        "INSERT INTO user_config (id, meals_per_week) VALUES ('user-1', 4)",
      );
      await live.close();
    });
    return h;
  }

  _settingsWidgetTest(
    'choosing a backup and confirming replaces the phone\'s data with it, using the signed link without the Cognito token',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.backups = <Map<String, Object?>>[
        _entry(id: 'db-exports/user-1/a/', url: _exportedUrl),
      ];
      h.downloads[_exportedUrl] = (await tester.runAsync(
        () => _backupBytes(dir, 'exported', mealsPerWeek: 7),
      ))!;
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      await _unlockDeveloperMode(tester);
      await tester.tap(find.byKey(_restoreButton));
      await _until(tester, 'database v2');
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('restore.backup.db-exports/user-1/a/')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('restore.confirm')));
      await _until(tester, 'Backup restored');

      expect(find.text('Backup restored'), findsOneWidget);
      expect(await mealsPerWeekOnDisk(tester, h), 7);
      final http.Request download = h.requests.last;
      expect(download.url.toString(), _exportedUrl);
      expect(download.headers.containsKey('Authorization'), isFalse);
      expect(h.tempRoot.listSync(), isEmpty);
    },
  );

  _settingsWidgetTest(
    'a backup from a newer schema is refused with a clear message and the phone\'s data is untouched',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.backups = <Map<String, Object?>>[
        _entry(id: 'db-exports/user-1/n/', url: _newerUrl, schemaVersion: 99),
      ];
      h.downloads[_newerUrl] = _newerBackupBytes(dir);
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      await _unlockDeveloperMode(tester);
      await tester.tap(find.byKey(_restoreButton));
      await _until(tester, 'database v99');
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('restore.backup.db-exports/user-1/n/')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('restore.confirm')));
      await _until(tester, 'newer version');

      expect(find.textContaining('newer version of Glean'), findsOneWidget);
      expect(await mealsPerWeekOnDisk(tester, h), 4);
      expect(h.tempRoot.listSync(), isEmpty);
    },
  );

  _settingsWidgetTest(
    'when the backups cannot be listed the user is told and nothing changes',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.listStatus = 500;
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      await _unlockDeveloperMode(tester);
      await tester.tap(find.byKey(_restoreButton));
      await _until(tester, 'Could not load backups');

      expect(find.text('Could not load backups. Try again.'), findsOneWidget);
      expect(await mealsPerWeekOnDisk(tester, h), 4);
    },
  );
}
