// AC-AUTH-04 (routing half): the redirect gates on `signedOut` only. A
// token expiry must not evict the user from their (local) data — the
// screen they're on stays exactly as it is.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/auth_state.dart';
import 'package:glean/router/router.dart';

Future<ProviderContainer> pumpApp(WidgetTester tester) async {
  final container = ProviderContainer();
  final router = container.read(goRouterProvider);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

void main() {
  testWidgets('signed out is gated to sign-in from the very first frame', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    // Flip status before the router is even built, proving the gate applies
    // on entry, not just on a later transition.
    container.read(authStatusProvider.notifier).setStatus(AuthStatus.signedOut);
    final router = container.read(goRouterProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsWidgets);
    expect(find.text('Pantry screen'), findsNothing);
  });

  testWidgets('expiry keeps the user on their current screen, no redirect', (
    tester,
  ) async {
    final container = await pumpApp(tester);
    expect(find.text('Pantry screen'), findsWidgets);

    container.read(authStatusProvider.notifier).setStatus(AuthStatus.expired);
    await tester.pumpAndSettle();

    expect(
      find.text('Pantry screen'),
      findsWidgets,
      reason: 'AC-AUTH-04: expiry must not route the user away from local data',
    );
    expect(find.text('Sign in'), findsNothing);
  });

  testWidgets('signing out while in the app redirects reactively', (
    tester,
  ) async {
    final container = await pumpApp(tester);
    expect(find.text('Pantry screen'), findsWidgets);

    container.read(authStatusProvider.notifier).setStatus(AuthStatus.signedOut);
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsWidgets);
  });

  testWidgets('landing on sign-in while already active sends you to Pantry', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final router = container.read(goRouterProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    router.go(AppRoutes.signIn.path);
    await tester.pumpAndSettle();

    expect(find.text('Pantry screen'), findsWidgets);
    expect(find.text('Sign in'), findsNothing);
  });
}
