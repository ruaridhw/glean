// `OnboardingGate` is the seam that decides whether the first-run flow
// shows at all — see its doc comment for the router wiring this still
// needs. These tests cover the gating logic in isolation: shown on first
// run, not shown once completed, and not shown again after a restart
// (simulated by remounting against the same status store).
//
// Pumped through the shared `AppTestHarness` (`test/support/harness.dart`)
// rather than a hand-rolled `MaterialApp` — a bare `MaterialApp` here
// previously failed with "gleanLightTheme must register an AppTokens
// ThemeExtension" because `OnboardingScreen` reads `context.tokens`. The
// harness is used for its theme/db/container wiring; `OnboardingGate` itself
// needs no `GoRouter`, so this builds its own root widget rather than
// `harness.app()` (which pumps the real routed app).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/onboarding/onboarding_gate.dart';
import 'package:glean/features/onboarding/onboarding_screen.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';

import '../../support/harness.dart';

const String _userId = 'user-1';
const Key _appHomeKey = Key('app.home');

Widget _buildApp(AppTestHarness harness) {
  return UncontrolledProviderScope(
    container: harness.container,
    child: MaterialApp(
      theme: gleanLightTheme,
      home: const OnboardingGate(
        child: Scaffold(key: _appHomeKey, body: Text('The real app')),
      ),
    ),
  );
}

void main() {
  testWidgets('shows the first-run flow when nothing has completed it yet', (
    WidgetTester tester,
  ) async {
    final harness = AppTestHarness(
      userId: _userId,
      onboardingStatusStore: InMemoryOnboardingStatusStore(),
    );
    addTearDown(harness.dispose);

    await tester.pumpWidget(_buildApp(harness));
    await tester.pump();
    await tester.pump();

    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.byKey(_appHomeKey), findsNothing);
  });

  testWidgets('shows the real app directly when onboarding is already done', (
    WidgetTester tester,
  ) async {
    final harness = AppTestHarness(
      userId: _userId,
      onboardingStatusStore: InMemoryOnboardingStatusStore(
        initiallyCompleted: <String>{_userId},
      ),
    );
    addTearDown(harness.dispose);

    await tester.pumpWidget(_buildApp(harness));
    await tester.pump();
    await tester.pump();

    expect(find.byType(OnboardingScreen), findsNothing);
    expect(find.byKey(_appHomeKey), findsOneWidget);
  });

  testWidgets(
    'does not show again after a restart once it has been completed',
    (WidgetTester tester) async {
      final store = InMemoryOnboardingStatusStore();
      final harness = AppTestHarness(
        userId: _userId,
        onboardingStatusStore: store,
      );
      addTearDown(harness.dispose);

      await tester.pumpWidget(_buildApp(harness));
      await tester.pump();
      await tester.pump();
      expect(find.byType(OnboardingScreen), findsOneWidget);

      await store.markCompleted(_userId);

      // Simulate an app restart: tear the whole tree down and remount a
      // fresh gate against the same (now-persisted) store and container.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(_buildApp(harness));
      await tester.pump();
      await tester.pump();

      expect(find.byType(OnboardingScreen), findsNothing);
      expect(find.byKey(_appHomeKey), findsOneWidget);
    },
  );
}
