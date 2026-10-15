// R-01 (.scratch/flutter-port/REMEDIATION.md): `OnboardingGate` existed,
// was tested in isolation, and nothing in the real router ever mounted it —
// a first-run user could open the app and land straight on Pantry with
// dinners/week, servings and dietary flags stuck at their defaults forever
// (AC-UX-04). These tests exercise the real `goRouterProvider` (via
// `AppTestHarness`, not a hand-built widget tree) so they fail if the
// `StatefulShellRoute.indexedStack` builder in `lib/router/router.dart`
// ever stops wrapping `AppShell` in `OnboardingGate` again.
//
// `AppTestHarness` defaults every test to "already onboarded" (see its own
// comment) precisely so the hundreds of other screen tests aren't gated —
// these tests are the ones that deliberately override that default back to
// "first run" to prove the gate is still wired.

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/onboarding/onboarding_screen.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/router/app_routes.dart';

import '../support/harness.dart';

void main() {
  testWidgets('a first-run user lands on setup, not the tab shell', (
    tester,
  ) async {
    final harness = AppTestHarness(
      onboardingStatusStore: InMemoryOnboardingStatusStore(),
    );
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pump();
    await tester.pump();

    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.byType(PantryScreen), findsNothing);
  });

  testWidgets('a returning user goes straight to Pantry', (tester) async {
    // Default harness: onboarding already completed for this user.
    final harness = AppTestHarness();
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();

    expect(find.byType(PantryScreen), findsOneWidget);
    expect(find.byType(OnboardingScreen), findsNothing);
  });

  testWidgets(
    'finishing setup swaps straight to Pantry with no route change needed',
    (tester) async {
      final harness = AppTestHarness(
        onboardingStatusStore: InMemoryOnboardingStatusStore(),
      );
      addTearDown(harness.dispose);

      await tester.pumpWidget(harness.app());
      await tester.pump();
      await tester.pump();
      expect(find.byType(OnboardingScreen), findsOneWidget);

      await tester.tap(find.text('Skip'));
      await tester.pump();
      await tester.pump();

      expect(find.byType(OnboardingScreen), findsNothing);
      expect(find.byType(PantryScreen), findsOneWidget);
    },
  );

  testWidgets(
    'deep-linking straight to another tab is still gated for a first-run user',
    (tester) async {
      final harness = AppTestHarness(
        onboardingStatusStore: InMemoryOnboardingStatusStore(),
      );
      addTearDown(harness.dispose);

      await harness.pumpAt(tester, AppRoutes.settings.path);
      await tester.pump();
      await tester.pump();

      expect(
        find.byType(OnboardingScreen),
        findsOneWidget,
        reason: 'the gate wraps every branch of the shell, not just Pantry',
      );
    },
  );
}
