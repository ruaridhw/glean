// Settings' developer-only Export diagnostics action: hidden until the version label is tapped 7 times, then
// uploads through the diagnostics export seam and reports where it landed.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/logging/logging.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:sqlite3/sqlite3.dart' as sqlite;

import '../../data/fixture.dart';

const Key _versionLabel = Key('settings.versionLabel');
const Key _exportButton = Key('settings.exportDiagnostics');

class _NoPlatformLog implements PlatformLogSink {
  @override
  Future<void> write({
    required String level,
    required String tag,
    required String message,
  }) async {}
}

/// Everything is real except the outside world: the HTTP client, the temp directory and the platform log.
class _Harness {
  _Harness(this.dir, this.backend) {
    tempRoot = Directory('${dir.path}/tmp')..createSync();
    logFile = RotatingLogFile(File('${dir.path}/glean.log'));
    logger = GleanLogger(file: logFile, platform: _NoPlatformLog());
  }

  final Directory dir;
  final Future<http.Response> Function(http.Request request) backend;
  late final Directory tempRoot;
  late final RotatingLogFile logFile;
  late final GleanLogger logger;
  final List<http.Request> requests = <http.Request>[];

  Widget app(GleanDatabase db) {
    return ProviderScope(
      overrides: [
        gleanDatabaseProvider.overrideWithValue(db),
        currentUserIdProvider.overrideWithValue('user-1'),
        gleanLoggerProvider.overrideWithValue(logger),
        diagnosticsTempDirProvider.overrideWithValue(() async => tempRoot),
        apiBaseUrlProvider.overrideWithValue('http://localhost:8000'),
        apiAccessTokenProvider.overrideWithValue(() async => 'test-token'),
        httpClientProvider.overrideWithValue(
          MockClient((http.Request request) {
            requests.add(request);
            return backend(request);
          }),
        ),
      ],
      child: MaterialApp(theme: gleanLightTheme, home: const SettingsScreen()),
    );
  }
}

/// The bytes of one named part of a multipart/form-data request.
Uint8List _part(http.Request request, String name) {
  final String boundary =
      '--${RegExp(r'boundary=(.+)$').firstMatch(request.headers['content-type']!)!.group(1)}';
  final Uint8List bytes = request.bodyBytes;
  final String raw = latin1.decode(
    bytes,
  ); // one char per byte, so string offsets are byte offsets
  final int header = raw.indexOf('name="$name"');
  final int start = raw.indexOf('\r\n\r\n', header) + 4;
  final int end = raw.indexOf('\r\n$boundary', start);
  return Uint8List.sublistView(bytes, start, end);
}

http.Response _stored(String prefix) => http.Response(
  jsonEncode(<String, Object?>{
    'status': 'uploaded',
    'prefix': prefix,
    'keys': <String, String>{},
  }),
  200,
);

Future<void> _waitForContent(WidgetTester tester) async {
  for (var i = 0; i < 30; i++) {
    await tester.pump(const Duration(milliseconds: 50));
    if (find.byType(SkeletonBox).evaluate().isEmpty) return;
  }
  fail('Settings content never appeared past the loading skeleton.');
}

// Unmounting inside the test lets drift's cleanup timer drain before the binding checks for pending timers.
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

/// Settings is a lazy list, so a control below the fold only exists once it has been scrolled to.
Future<void> _reveal(WidgetTester tester, Key key) async {
  await tester.scrollUntilVisible(
    find.byKey(key),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pump();
}

Future<void> _tapVersionLabel(WidgetTester tester, int times) async {
  await _reveal(tester, _versionLabel);
  for (var i = 0; i < times; i++) {
    await tester.tap(find.byKey(_versionLabel));
    await tester.pump();
  }
}

void main() {
  late GleanDatabase db;
  late Directory dir;

  setUp(() {
    db = createTestDatabase();
    dir = Directory.systemTemp.createTempSync('glean_export_ui_test');
    PackageInfo.setMockInitialValues(
      appName: 'Glean',
      packageName: 'com.ruaridhw.glean',
      version: '1.0.0',
      buildNumber: '1474560',
      buildSignature: '',
    );
  });
  tearDown(() async {
    await db.close();
    dir.deleteSync(recursive: true);
  });

  /// Taps Export diagnostics, then lets the real file and database work finish outside the fake-async zone.
  Future<void> exportAndWait(WidgetTester tester, String expectedText) async {
    await tester.tap(find.byKey(_exportButton));
    await tester.pump();
    for (
      var i = 0;
      i < 40 && find.textContaining(expectedText).evaluate().isEmpty;
      i++
    ) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pump();
    }
  }

  _settingsWidgetTest(
    'the version label shows the version and build number, and export is hidden',
    (tester) async {
      final _Harness h = _Harness(dir, (_) async => _stored('unused'));
      await tester.pumpWidget(h.app(db));
      await _waitForContent(tester);
      await _reveal(tester, _versionLabel);

      expect(find.text('Glean 1.0.0 (1474560)'), findsOneWidget);
      expect(find.byKey(_exportButton), findsNothing);
    },
  );

  _settingsWidgetTest(
    'six taps on the version label keep Export diagnostics hidden; the seventh reveals it',
    (tester) async {
      final _Harness h = _Harness(dir, (_) async => _stored('unused'));
      await tester.pumpWidget(h.app(db));
      await _waitForContent(tester);

      await _tapVersionLabel(tester, 6);
      expect(find.byKey(_exportButton), findsNothing);

      await _tapVersionLabel(tester, 1);
      await _reveal(tester, _exportButton);
      expect(find.byKey(_exportButton), findsOneWidget);
    },
  );

  _settingsWidgetTest(
    'exporting uploads the real database snapshot and log, cleans up, and shows where it landed',
    (tester) async {
      final _Harness h = _Harness(
        dir,
        (_) async => _stored('db-exports/user-1/20261015T120000000000Z/'),
      );
      h.logFile.append(
        '2026-10-15T12:00:00.000Z error earlier failure on /recipes/search',
      );
      await tester.runAsync(
        () => db.customStatement(
          "INSERT INTO user_config (id, meals_per_week) VALUES ('user-1', 4)",
        ),
      );
      await tester.pumpWidget(h.app(db));
      await _waitForContent(tester);
      await _tapVersionLabel(tester, 7);
      await _reveal(tester, _exportButton);

      await exportAndWait(tester, 'db-exports/user-1/');

      expect(
        find.textContaining('db-exports/user-1/20261015T120000000000Z/'),
        findsOneWidget,
      );
      final http.Request request = h.requests.single;
      expect(request.url.path, '/dev/export-db');
      expect(request.headers['Authorization'], 'Bearer test-token');
      final File uploaded = File('${dir.path}/uploaded.sqlite')
        ..writeAsBytesSync(_part(request, 'database'));
      final sqlite.Database copy = sqlite.sqlite3.open(uploaded.path);
      addTearDown(copy.close);
      expect(copy.select('PRAGMA integrity_check').single.values, <Object?>[
        'ok',
      ]);
      expect(
        copy
            .select('SELECT meals_per_week FROM user_config')
            .single['meals_per_week'],
        4,
      );
      expect(
        utf8.decode(_part(request, 'log')),
        contains('earlier failure on /recipes/search'),
      );
      expect(
        h.tempRoot.listSync(),
        isEmpty,
        reason: 'the snapshot is a copy of the user data and must not linger',
      );
    },
  );

  _settingsWidgetTest(
    'a rejected upload is shown to the user, logged without the response, and leaves no snapshot behind',
    (tester) async {
      final _Harness h = _Harness(
        dir,
        (_) async => http.Response('{"detail":"token opaque-secret-123"}', 500),
      );
      await tester.pumpWidget(h.app(db));
      await _waitForContent(tester);
      await _tapVersionLabel(tester, 7);
      await _reveal(tester, _exportButton);

      await exportAndWait(tester, 'Could not export diagnostics');

      expect(
        find.text('Could not export diagnostics. Try again.'),
        findsOneWidget,
      );
      expect(h.logFile.readAll(), contains('ApiServerException: HTTP 500'));
      expect(h.logFile.readAll(), isNot(contains('opaque-secret-123')));
      expect(h.tempRoot.listSync(), isEmpty);
    },
  );

  _settingsWidgetTest(
    'a garbled success response is logged without its body or any token in it',
    (tester) async {
      final _Harness h = _Harness(
        dir,
        (_) async => http.Response(
          '<html>refresh_token=opaque-secret-123 private-receipt-note</html>',
          200,
        ),
      );
      await tester.pumpWidget(h.app(db));
      await _waitForContent(tester);
      await _tapVersionLabel(tester, 7);
      await _reveal(tester, _exportButton);

      await exportAndWait(tester, 'Could not export diagnostics');

      final String logged = h.logFile.readAll();
      expect(logged, contains('ApiParseException'));
      expect(logged, isNot(contains('opaque-secret-123')));
      expect(logged, isNot(contains('private-receipt-note')));
    },
  );
}
