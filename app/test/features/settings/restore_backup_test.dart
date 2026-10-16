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
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/pantry_providers.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/providers/recipes_providers.dart';
import 'package:glean/data/providers/shopping_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/diagnostics/diagnostics.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/features/settings/widgets/settings_stats_row.dart';
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
          ref.onDispose(() => closeDatabase(db));
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

final DateTime _week = startOfWeek(DateTime(2026, 1, 5));

/// Everything the app shows for the user, read through the real providers: what a restore must bring back.
Future<Map<String, Object?>> _domainState(
  WidgetTester tester,
  ProviderContainer container,
) async {
  // Riverpod pauses a stream provider nobody listens to, and these sit on a database opened inside the test's
  // fake-async zone, so they only advance while listened to and pumped.
  final List<ProviderSubscription<Object?>> listeners =
      <ProviderSubscription<Object?>>[
        container.listen(pantryItemsProvider, (_, _) {}),
        container.listen(shoppingListProvider, (_, _) {}),
        container.listen(savedRecipesProvider, (_, _) {}),
        container.listen(planWeekProvider(_week), (_, _) {}),
        container.listen(userConfigProvider, (_, _) {}),
      ];
  for (var i = 0; i < 60; i++) {
    final List<AsyncValue<Object?>> reads = <AsyncValue<Object?>>[
      container.read(pantryItemsProvider),
      container.read(shoppingListProvider),
      container.read(savedRecipesProvider),
      container.read(planWeekProvider(_week)),
      container.read(userConfigProvider),
    ];
    if (reads.every((AsyncValue<Object?> r) => r.hasValue && !r.isLoading)) {
      break;
    }
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 50));
  }
  final pantry = container.read(pantryItemsProvider).requireValue;
  final shopping = container.read(shoppingListProvider).requireValue;
  final recipes = container.read(savedRecipesProvider).requireValue;
  final plan = container.read(planWeekProvider(_week)).requireValue;
  final config = container.read(userConfigProvider).requireValue;
  for (final ProviderSubscription<Object?> l in listeners) {
    l.close();
  }
  return <String, Object?>{
    'pantry': <String>[
      for (final i in pantry) '${i.canonicalName} ${i.quantity}${i.unit}',
    ],
    'shopping': <String>[for (final i in shopping) i.name],
    'recipes': <String>[for (final r in recipes) r.title],
    'plan': <String>[
      for (final e in plan) '${e.recipeTitle}${e.isCooked ? ' (cooked)' : ''}',
    ],
    'mealsPerWeek': config.mealsPerWeek,
  };
}

const Map<String, Object?> _liveState = <String, Object?>{
  'pantry': <String>['rice 300.0g'],
  'shopping': <String>[],
  'recipes': <String>[],
  'plan': <String>[],
  'mealsPerWeek': 4,
};

const Map<String, Object?> _backedUpState = <String, Object?>{
  'pantry': <String>['chicken breast 300.0g'],
  'shopping': <String>['oat milk'],
  'recipes': <String>['Chicken dinner'],
  'plan': <String>['Chicken dinner (cooked)', 'Chicken dinner'],
  'mealsPerWeek': 7,
};

Future<void> _setMealsPerWeek(GleanDatabase db, int n) =>
    UserConfigRepository(db).save(
      UserConfigView(
        id: 'user-1',
        purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
        preferredServings: UserConfigView.defaultPreferredServings,
        mealsPerWeek: n,
        dietaryFlags: const <String>[],
        maxActiveTimeMins: null,
      ),
    );

/// The phone's own data before a restore: one pantry item and the default-ish settings.
Future<void> _seedLive(GleanDatabase db) async {
  await PantryRepository(db, IngredientsRepository(db)).addItem(
    userId: 'user-1',
    name: 'rice',
    quantity: 300,
    unit: 'g',
    category: 'poultry',
  );
  await _setMealsPerWeek(db, 4);
}

/// A backup holding every part of the user's state: pantry, shopping list, saved recipe, a cooked and an
/// uncooked plan entry (history) and settings. Written through the repositories, closed, returned as bytes.
Future<List<int>> _fullBackupBytes(Directory dir, String name) async {
  final File file = File('${dir.path}/$name.sqlite');
  final GleanDatabase db = GleanDatabase(NativeDatabase(file));
  final IngredientsRepository ingredients = IngredientsRepository(db);
  final PantryRepository pantry = PantryRepository(db, ingredients);
  final PlanRepository plan = PlanRepository(db, pantry);
  await pantry.addItem(
    userId: 'user-1',
    name: 'chicken breast',
    quantity: 500,
    unit: 'g',
    category: 'poultry',
    now: DateTime(2026, 1, 1),
  );
  await ShoppingRepository(
    db,
    ingredients,
  ).addManualItem(userId: 'user-1', name: 'oat milk');
  final int recipeId = await RecipesRepository(db, ingredients).save(
    userId: 'user-1',
    title: 'Chicken dinner',
    ingredients: const <SaveRecipeIngredient>[
      SaveRecipeIngredient(
        canonicalName: 'chicken breast',
        quantity: 100,
        unit: 'g',
      ),
    ],
  );
  final int cooked = await plan.addEntry(
    userId: 'user-1',
    recipeId: recipeId,
    recipeTitle: 'Chicken dinner',
    servings: 2,
    plannedDate: _week,
  );
  await plan.addEntry(
    userId: 'user-1',
    recipeId: recipeId,
    recipeTitle: 'Chicken dinner',
    servings: 2,
    plannedDate: _week.add(const Duration(days: 1)),
  );
  await plan.markCooked(
    entryId: cooked,
    userId: 'user-1',
    now: DateTime(2026, 1, 6),
  );
  await _setMealsPerWeek(db, 7);
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

  Future<_Harness> openedWithLiveData(WidgetTester tester) async {
    final _Harness h = _Harness(dir);
    await tester.runAsync(() async {
      final GleanDatabase live = GleanDatabase(NativeDatabase(h.liveFile));
      await _seedLive(live);
      await live.close();
    });
    return h;
  }

  ProviderContainer containerOf(WidgetTester tester) =>
      ProviderScope.containerOf(tester.element(find.byType(SettingsScreen)));

  Future<void> chooseAndConfirm(
    WidgetTester tester,
    String id,
    String sheetText,
  ) async {
    await tester.tap(find.byKey(_restoreButton));
    await _until(tester, sheetText);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(Key('restore.backup.$id')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('restore.confirm')));
  }

  _settingsWidgetTest(
    'restoring a backup brings back the pantry, shopping list, recipes, plan, cooking history and settings through the app\'s own providers and screen',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.backups = <Map<String, Object?>>[
        _entry(id: 'db-exports/user-1/a/', url: _exportedUrl),
      ];
      h.downloads[_exportedUrl] = (await tester.runAsync(
        () => _fullBackupBytes(dir, 'exported'),
      ))!;
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      expect(await _domainState(tester, containerOf(tester)), _liveState);
      await _unlockDeveloperMode(tester);

      await chooseAndConfirm(tester, 'db-exports/user-1/a/', 'database v2');
      await _until(tester, 'Backup restored');
      expect(find.text('Backup restored'), findsOneWidget);
      await _waitForContent(tester);

      expect(await _domainState(tester, containerOf(tester)), _backedUpState);
      expect(
        find.descendant(
          of: find.byType(SettingsStatsRow),
          matching: find.text('7'),
        ),
        findsOneWidget,
        reason: 'the Settings summary shows the restored dinners per week',
      );
      final http.Request download = h.requests.last;
      expect(download.url.toString(), _exportedUrl);
      expect(download.headers.containsKey('Authorization'), isFalse);
      expect(h.tempRoot.listSync(), isEmpty);
    },
  );

  _settingsWidgetTest(
    'a backup from a newer schema is refused with a clear message and every part of the phone\'s data is still shown',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.backups = <Map<String, Object?>>[
        _entry(id: 'db-exports/user-1/n/', url: _newerUrl, schemaVersion: 99),
      ];
      h.downloads[_newerUrl] = _newerBackupBytes(dir);
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      await _unlockDeveloperMode(tester);

      await chooseAndConfirm(tester, 'db-exports/user-1/n/', 'database v99');
      await _until(tester, 'newer version');

      expect(find.textContaining('newer version of Glean'), findsOneWidget);
      expect(await _domainState(tester, containerOf(tester)), _liveState);
      expect(h.tempRoot.listSync(), isEmpty);
    },
  );

  _settingsWidgetTest(
    'a restore that fails after the old connection closed reopens the previous database so the app keeps working',
    (tester) async {
      final _Harness h = await openedWithLiveData(tester);
      h.backups = <Map<String, Object?>>[
        _entry(id: 'db-exports/user-1/a/', url: _exportedUrl),
      ];
      h.downloads[_exportedUrl] = (await tester.runAsync(
        () => _fullBackupBytes(dir, 'exported'),
      ))!;
      // The kept copy of the previous database cannot be written, which only fails once the live connection
      // is already closed.
      Directory('${h.liveFile.path}.pre-restore').createSync();
      await tester.pumpWidget(h.app());
      await _waitForContent(tester);
      await _unlockDeveloperMode(tester);

      await chooseAndConfirm(tester, 'db-exports/user-1/a/', 'database v2');
      await _until(tester, 'Could not restore the backup');
      await _waitForContent(tester);

      expect(
        find.textContaining('Could not restore the backup'),
        findsOneWidget,
      );
      expect(await _domainState(tester, containerOf(tester)), _liveState);
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
      expect(await _domainState(tester, containerOf(tester)), _liveState);
    },
  );
}
