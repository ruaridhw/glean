// `OnboardingGate` is the seam that decides whether the first-run flow
// shows at all — see its doc comment for the router wiring this still
// needs. These tests cover the gating logic in isolation: shown on first
// run, not shown once completed, and not shown again after a restart
// (simulated by remounting against the same status store).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/features/onboarding/onboarding_gate.dart';
import 'package:glean/features/onboarding/onboarding_screen.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';

const String _userId = 'user-1';
const Key _appHomeKey = Key('app.home');

Widget _buildApp(InMemoryOnboardingStatusStore store) {
  return ProviderScope(
    overrides: [
      currentUserIdProvider.overrideWithValue(_userId),
      onboardingStatusStoreProvider.overrideWithValue(store),
    ],
    child: const MaterialApp(
      home: OnboardingGate(
        child: Scaffold(key: _appHomeKey, body: Text('The real app')),
      ),
    ),
  );
}

void main() {
  testWidgets('shows the first-run flow when nothing has completed it yet', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(_buildApp(InMemoryOnboardingStatusStore()));
    await tester.pump();
    await tester.pump();

    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.byKey(_appHomeKey), findsNothing);
  });

  testWidgets('shows the real app directly when onboarding is already done', (
    WidgetTester tester,
  ) async {
    final store = InMemoryOnboardingStatusStore(
      initiallyCompleted: <String>{_userId},
    );
    await tester.pumpWidget(_buildApp(store));
    await tester.pump();
    await tester.pump();

    expect(find.byType(OnboardingScreen), findsNothing);
    expect(find.byKey(_appHomeKey), findsOneWidget);
  });

  testWidgets(
    'does not show again after a restart once it has been completed',
    (WidgetTester tester) async {
      final store = InMemoryOnboardingStatusStore();
      await tester.pumpWidget(_buildApp(store));
      await tester.pump();
      await tester.pump();
      expect(find.byType(OnboardingScreen), findsOneWidget);

      await store.markCompleted(_userId);

      // Simulate an app restart: tear the whole tree down and remount a
      // fresh gate against the same (now-persisted) store.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpWidget(_buildApp(store));
      await tester.pump();
      await tester.pump();

      expect(find.byType(OnboardingScreen), findsNothing);
      expect(find.byKey(_appHomeKey), findsOneWidget);
    },
  );
}
