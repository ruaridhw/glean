// Shared widget-test harness for the Meals feature. Not a test suite itself
// (no `_test.dart` suffix) — `flutter test` never picks it up directly.
//
// Meals screens navigate through the real route table (`context.pushNamed`,
// `context.go`), so pumping a bare `MaterialApp(home: ...)` with no
// `GoRouter` in the tree would throw the moment a tap tries to navigate.
// This mirrors `test/router/*.dart`'s own harness: a real `goRouterProvider`
// over an in-memory drift database, so every screen under test exercises
// its actual navigation and data wiring rather than a stand-in.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/router.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;

import '../../data/fixture.dart';

class MealsTestHarness {
  MealsTestHarness({
    String userId = 'user-a',
    http.Client? httpClient,
    Haptics? haptics,
  }) : db = createTestDatabase() {
    container = ProviderContainer(
      // Note: `Override` (the list's documented element type) isn't
      // importable from `flutter_riverpod` in this version (FINDINGS.md
      // F-03) — left untyped and inferred contextually.
      overrides: [
        gleanDatabaseProvider.overrideWithValue(db),
        currentUserIdProvider.overrideWithValue(userId),
        apiBaseUrlProvider.overrideWithValue('http://localhost:9999'),
        if (haptics != null) hapticsProvider.overrideWithValue(haptics),
        if (httpClient != null)
          httpClientProvider.overrideWithValue(httpClient),
      ],
    );
    router = container.read(goRouterProvider);
  }

  final GleanDatabase db;
  late final ProviderContainer container;
  late final GoRouter router;

  Widget app() {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router, theme: gleanLightTheme),
    );
  }

  /// Navigates to [location] and pumps a fresh app instance there — the same
  /// pattern `test/router/route_table_test.dart`'s `pumpAt` uses.
  Future<void> pumpAt(WidgetTester tester, String location) async {
    router.go(location);
    await tester.pumpWidget(app());
    await tester.pumpAndSettle();
  }

  Future<void> dispose() async {
    container.dispose();
    await db.close();
  }
}
