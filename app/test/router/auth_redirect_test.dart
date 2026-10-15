// The redirect gates on `signedOut` only. A token expiry must not evict the
// user from their (local) data — the screen they're on stays exactly as it is.

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/features/auth/sign_in_screen.dart';
import 'package:glean/features/intake/manual_entry_screen.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/router/app_routes.dart';

import '../support/harness.dart';

void main() {
  testWidgets('signed out is gated to sign-in from the very first frame', (
    tester,
  ) async {
    // Seeded signed out before the router has ever resolved a location —
    // the same cold-start shape `loadInitialAuthSnapshot` produces.
    final harness = AppTestHarness(authStatus: AuthStatus.signedOut);
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();

    expect(find.byType(SignInScreen), findsOneWidget);
    expect(find.byType(PantryScreen), findsNothing);
  });

  testWidgets('expiry keeps the user on their current screen, no redirect', (
    tester,
  ) async {
    final harness = AppTestHarness();
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
    expect(find.byType(PantryScreen), findsOneWidget);

    harness.container
        .read(authControllerProvider.notifier)
        .debugSetSnapshot(
          AuthSessionSnapshot(
            status: AuthStatus.expired,
            userId: harness.userId,
          ),
        );
    await tester.pumpAndSettle();

    expect(
      find.byType(PantryScreen),
      findsOneWidget,
      reason: 'expiry must not route the user away from local data',
    );
    expect(find.byType(SignInScreen), findsNothing);
  });

  testWidgets('signing out while in the app redirects reactively', (
    tester,
  ) async {
    final harness = AppTestHarness();
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
    expect(find.byType(PantryScreen), findsOneWidget);

    await harness.container.read(authControllerProvider.notifier).signOut();
    await tester.pumpAndSettle();

    expect(find.byType(SignInScreen), findsOneWidget);
  });

  testWidgets(
    'signing out redirects even when nothing on screen watches auth',
    (tester) async {
      // Manual entry sits outside the tab shell and shows no signed-out banner,
      // so the router's own auth listener is the only thing that can redirect.
      final harness = AppTestHarness();
      addTearDown(harness.dispose);

      await harness.pumpAt(tester, AppRoutes.intakeManualEntry.path);
      await tester.pumpAndSettle();
      expect(find.byType(ManualEntryScreen), findsOneWidget);

      await harness.container.read(authControllerProvider.notifier).signOut();
      await tester.pumpAndSettle();

      expect(harness.router.state.matchedLocation, AppRoutes.signIn.path);
      expect(find.byType(SignInScreen), findsOneWidget);
    },
  );

  testWidgets('landing on sign-in while already active sends you to Pantry', (
    tester,
  ) async {
    final harness = AppTestHarness();
    addTearDown(harness.dispose);

    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();

    harness.router.go(AppRoutes.signIn.path);
    await tester.pumpAndSettle();

    expect(find.byType(PantryScreen), findsOneWidget);
    expect(find.byType(SignInScreen), findsNothing);
  });
}
