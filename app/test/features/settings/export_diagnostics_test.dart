// Settings' developer-only Export diagnostics action: hidden until the version label is tapped 7 times, then
// uploads through the diagnostics export seam and reports where it landed.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/logging/logging.dart';
import 'package:package_info_plus/package_info_plus.dart';

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

Widget _buildApp({
  required GleanDatabase db,
  required DiagnosticsExport export,
  GleanLogger? logger,
}) {
  return ProviderScope(
    overrides: [
      gleanDatabaseProvider.overrideWithValue(db),
      currentUserIdProvider.overrideWithValue('user-1'),
      diagnosticsExportProvider.overrideWithValue(export),
      if (logger != null) gleanLoggerProvider.overrideWithValue(logger),
    ],
    child: MaterialApp(theme: gleanLightTheme, home: const SettingsScreen()),
  );
}

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

  setUp(() {
    db = createTestDatabase();
    PackageInfo.setMockInitialValues(
      appName: 'Glean',
      packageName: 'com.ruaridhw.glean',
      version: '1.0.0',
      buildNumber: '1474560',
      buildSignature: '',
    );
  });
  tearDown(() => db.close());

  _settingsWidgetTest(
    'the version label shows the version and build number, and export is hidden',
    (tester) async {
      await tester.pumpWidget(_buildApp(db: db, export: () async => 'unused'));
      await _waitForContent(tester);
      await _reveal(tester, _versionLabel);

      expect(find.text('Glean 1.0.0 (1474560)'), findsOneWidget);
      expect(find.byKey(_exportButton), findsNothing);
    },
  );

  _settingsWidgetTest(
    'six taps on the version label keep Export diagnostics hidden; the seventh reveals it',
    (tester) async {
      await tester.pumpWidget(_buildApp(db: db, export: () async => 'unused'));
      await _waitForContent(tester);

      await _tapVersionLabel(tester, 6);
      expect(find.byKey(_exportButton), findsNothing);

      await _tapVersionLabel(tester, 1);
      await _reveal(tester, _exportButton);
      expect(find.byKey(_exportButton), findsOneWidget);
    },
  );

  _settingsWidgetTest(
    'exporting uploads once and tells the user where it landed',
    (tester) async {
      var uploads = 0;
      await tester.pumpWidget(
        _buildApp(
          db: db,
          export: () async {
            uploads++;
            return 'db-exports/user-1/20261015T120000000000Z/';
          },
        ),
      );
      await _waitForContent(tester);
      await _tapVersionLabel(tester, 7);
      await _reveal(tester, _exportButton);

      await tester.tap(find.byKey(_exportButton));
      await tester.pump();
      await tester.pump();

      expect(uploads, 1);
      expect(
        find.textContaining('db-exports/user-1/20261015T120000000000Z/'),
        findsOneWidget,
      );
    },
  );

  _settingsWidgetTest(
    'a failed export is shown to the user and written to the log',
    (tester) async {
      final Directory dir = Directory.systemTemp.createTempSync(
        'glean_export_ui_test',
      );
      addTearDown(() => dir.deleteSync(recursive: true));
      final RotatingLogFile logFile = RotatingLogFile(
        File('${dir.path}/glean.log'),
      );
      await tester.pumpWidget(
        _buildApp(
          db: db,
          export: () async => throw StateError('upload refused'),
          logger: GleanLogger(file: logFile, platform: _NoPlatformLog()),
        ),
      );
      await _waitForContent(tester);
      await _tapVersionLabel(tester, 7);
      await _reveal(tester, _exportButton);

      await tester.tap(find.byKey(_exportButton));
      await tester.pump();
      await tester.pump();

      expect(
        find.text('Could not export diagnostics. Try again.'),
        findsOneWidget,
      );
      expect(logFile.readAll(), contains('upload refused'));
    },
  );
}
