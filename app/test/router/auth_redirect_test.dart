// AC-AUTH-04 (routing half): the redirect gates on `signedOut` only. A
// token expiry must not evict the user from their (local) data — the
// screen they're on stays exactly as it is.

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/auth/sign_in_screen.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/auth_state.dart';

import '../support/harness.dart';

/// Seeds [authStatusProvider] as `signedOut` from its very first `build()`,
/// so the redirect can be exercised before the router (and therefore
/// anything else) has ever resolved a location — mirrors the real
/// `SeededAuthStatusNotifier` AUTH now uses to seed real cold-start state
/// (`lib/auth/auth_controller.dart`).
class _SignedOutFromStart extends AuthStatusNotifier {
  @override
  AuthStatus build() => AuthStatus.signedOut;
}

void main() {
  testWidgets('signed out is gated to sign-in from the very first frame', (
    tester,
  ) async {
    final harness = AppTestHarness(
      overrides: [authStatusProvider.overrideWith(_SignedOutFromStart.new)],
    );
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
        .read(authStatusProvider.notifier)
        .setStatus(AuthStatus.expired);
    await tester.pumpAndSettle();

    expect(
      find.byType(PantryScreen),
      findsOneWidget,
      reason: 'AC-AUTH-04: expiry must not route the user away from local data',
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

    harness.container
        .read(authStatusProvider.notifier)
        .setStatus(AuthStatus.signedOut);
    await tester.pumpAndSettle();

    expect(find.byType(SignInScreen), findsOneWidget);
  });

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
