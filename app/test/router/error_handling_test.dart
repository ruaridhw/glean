// A cold-start deep link to a missing/unknown route must show a recoverable
// error, never a permanent spinner and never a `pop()` on an empty stack
// (§11, AC-MEAL-12's routing half).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/router.dart';

void main() {
  testWidgets(
    'an unmatched location hits errorBuilder with a working back affordance',
    (tester) async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final router = container.read(goRouterProvider);

      // Simulates a cold start: go() straight to a bogus location with no
      // prior stack to pop, exactly as a dead deep link would.
      router.go('/this-does-not-exist');

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      final backButton = find.widgetWithText(FilledButton, 'Back to Pantry');
      expect(backButton, findsOneWidget);

      await tester.tap(backButton);
      await tester.pumpAndSettle();

      expect(find.text('Pantry screen'), findsWidgets);
    },
  );

  testWidgets(
    'a malformed recipe id redirects to the error page, not a crash',
    (tester) async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final router = container.read(goRouterProvider);

      router.go(AppRoutes.mealsDetailPath('not-a-number'));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);

      await tester.tap(find.widgetWithText(FilledButton, 'Back to Pantry'));
      await tester.pumpAndSettle();

      expect(find.text('Pantry screen'), findsWidgets);
    },
  );

  testWidgets('a valid recipe id resolves normally (no false-positive error)', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final router = container.read(goRouterProvider);

    router.go(AppRoutes.mealsDetailPath('7'));

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Recipe 7'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline_rounded), findsNothing);
  });
}
