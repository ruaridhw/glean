// The shared widget-test harness. Not a test suite itself (no `_test.dart`
// suffix), so `flutter test` never picks it up directly.
//
// Every feature widget test should pump through this rather than building its
// own. Two reasons, both learned the hard way:
//
//  1. **The theme is not optional.** A bare `MaterialApp` registers no
//     `AppTokens` extension, so the first widget to read `context.tokens`
//     throws `gleanLightTheme must register an AppTokens ThemeExtension` at
//     build time. Several suites failed exactly this way before this existed.
//  2. **Screens navigate for real.** They call `context.pushNamed`/`context.go`
//     against the actual route table, so a harness without a `GoRouter` in the
//     tree throws the moment a tap tries to navigate. Pumping the real router
//     over a real in-memory database means a screen test exercises its genuine
//     navigation and data wiring instead of a stand-in.
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
import 'package:meta/meta.dart';
// `Override` is only exported from riverpod's `misc.dart` entrypoint, not from
// the `flutter_riverpod` barrel. `riverpod` is a direct dependency precisely so
// this import is legitimate — see FINDINGS.md F-03.
import 'package:riverpod/misc.dart';

import '../data/fixture.dart';

class AppTestHarness {
  AppTestHarness({
    this.userId = 'test-user',
    http.Client? httpClient,
    Haptics? haptics,
    List<Override> overrides = const <Override>[],
  }) : haptics = haptics ?? RecordingHaptics(),
       db = createTestDatabase() {
    container = ProviderContainer(
      overrides: <Override>[
        gleanDatabaseProvider.overrideWithValue(db),
        currentUserIdProvider.overrideWithValue(userId),
        // Deliberately unroutable: a test that accidentally performs a real
        // request should fail fast rather than reach the network.
        apiBaseUrlProvider.overrideWithValue('http://localhost:9999'),
        hapticsProvider.overrideWithValue(this.haptics),
        if (httpClient != null)
          httpClientProvider.overrideWithValue(httpClient),
        ...overrides,
      ],
    );
    router = container.read(goRouterProvider);
  }

  final String userId;
  final GleanDatabase db;

  /// Defaults to a [RecordingHaptics] so any test can assert the ladder
  /// (AC-HAP-01..05) without extra setup.
  final Haptics haptics;

  late final ProviderContainer container;
  late final GoRouter router;

  /// The recorded haptic weights, when [haptics] is the default recorder.
  List<HapticWeight> get hapticCalls => (haptics as RecordingHaptics).calls;

  Widget app() {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: router,
        theme: gleanLightTheme,
        debugShowCheckedModeBanner: false,
      ),
    );
  }

  /// Navigates to [location] and pumps a fresh app instance there.
  Future<void> pumpAt(WidgetTester tester, String location) async {
    router.go(location);
    await tester.pumpWidget(app());
    await tester.pump();
  }

  /// Call from `addTearDown` so the in-memory database and provider graph are
  /// released between tests — a leaked drift connection surfaces later as an
  /// unrelated-looking failure in a different suite.
  Future<void> dispose() async {
    container.dispose();
    await db.close();
  }
}

/// Unmounts the widget tree and drains the timer drift schedules while tearing
/// down its stream subscriptions.
///
/// **Any widget test whose tree holds a drift `.watch()` subscription must end
/// with this**, or the test wedges the whole isolate — see the wrapper below and
/// `.scratch/flutter-port/FINDINGS.md` F-12.
///
/// Unmounting disposes the `ProviderScope`, which disposes the `StreamProvider`
/// element, which cancels the drift stream — and `StreamQueryStore.markAsClosed`
/// schedules a zero-duration timer to finish its bookkeeping. Left pending, that
/// trips `!timersPending` and then hangs the isolate, so the entire *file* times
/// out rather than just the offending test.
///
/// Both details below are load-bearing and were each got wrong once:
///  * A **`pump`**, not `runAsync`. The timer is a `FakeTimer`, so `runAsync`
///    steps outside the very zone that would service it.
///  * A **non-zero** advance. The timer is scheduled *during* the unmount pump,
///    so a zero-duration advance does not reach it.
Future<void> releaseDriftTree(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  await tester.pump(const Duration(milliseconds: 1));
}

/// Pumps in fixed steps until [condition] holds, then returns.
///
/// **Use this instead of `pumpAndSettle` anywhere a skeleton or an indeterminate
/// progress indicator may be on screen.** Both are *required* to animate
/// perpetually (AC-DS-11 puts `SkeletonBox` on a `TweenAnimationBuilder`, and
/// AC-PAN-06 requires a genuinely indeterminate scan indicator), so
/// `pumpAndSettle` has no quiescent frame to settle on and times out — which
/// reads as a hang, not as a clear failure. A correct implementation is exactly
/// what makes `pumpAndSettle` unusable here.
Future<void> pumpUntil(
  WidgetTester tester,
  bool Function() condition, {
  Duration step = const Duration(milliseconds: 50),
  int maxSteps = 40,
  String description = 'condition',
}) async {
  for (int i = 0; i < maxSteps; i++) {
    await tester.pump(step);
    if (condition()) return;
  }
  fail('pumpUntil: $description never became true within $maxSteps pumps.');
}

/// Pumps until every [SkeletonBox] has been swapped out for real content.
Future<void> pumpPastSkeleton(WidgetTester tester) => pumpUntil(
  tester,
  () => find.byType(SkeletonBox).evaluate().isEmpty,
  description: 'content past the loading skeleton',
);

/// `testWidgets` that always releases the tree, even if the body throws.
///
/// The release must happen **inside** the test body: the binding verifies
/// `!timersPending` *before* any `addTearDown` callback runs, so registering the
/// cleanup as a teardown is too late — verified, it still trips the assertion.
@isTest
void gleanWidgetTest(
  String description,
  Future<void> Function(WidgetTester tester) body,
) {
  testWidgets(description, (WidgetTester tester) async {
    try {
      await body(tester);
    } finally {
      await releaseDriftTree(tester);
    }
  });
}
