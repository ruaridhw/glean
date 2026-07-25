// A cold-start deep link to a missing/unknown route must show a recoverable
// error, never a permanent spinner and never a `pop()` on an empty stack
// (§11, AC-MEAL-12's routing half).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/meals/meal_detail_screen.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/route_error_screen.dart';

import '../support/harness.dart';

void main() {
  late AppTestHarness harness;

  setUp(() {
    harness = AppTestHarness();
  });

  tearDown(() => harness.dispose());

  testWidgets(
    'an unmatched location hits errorBuilder with a working back affordance',
    (tester) async {
      // Simulates a cold start: navigate straight to a bogus location with
      // no prior stack to pop, exactly as a dead deep link would.
      await harness.pumpAt(tester, '/this-does-not-exist');
      await tester.pumpAndSettle();

      expect(find.byType(RouteErrorScreen), findsOneWidget);
      final backButton = find.widgetWithText(FilledButton, 'Back to Pantry');
      expect(backButton, findsOneWidget);

      await tester.tap(backButton);
      await tester.pumpAndSettle();

      expect(find.byType(PantryScreen), findsOneWidget);
    },
  );

  testWidgets(
    'a malformed recipe id redirects to the error page before ever reaching the screen',
    (tester) async {
      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('not-a-number'));
      await tester.pumpAndSettle();

      expect(find.byType(RouteErrorScreen), findsOneWidget);
      expect(
        find.byType(MealDetailScreen),
        findsNothing,
        reason: "the router's redirect guard must reject this before it builds",
      );

      await tester.tap(find.widgetWithText(FilledButton, 'Back to Pantry'));
      await tester.pumpAndSettle();

      expect(find.byType(PantryScreen), findsOneWidget);
    },
  );

  testWidgets(
    'a syntactically valid recipe id is routed through, not redirected',
    (tester) async {
      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('7'));
      await tester.pumpAndSettle();

      // Whether recipe 7 actually exists is a data/feature concern, not
      // routing's — a fresh fixture has no such recipe, and
      // MealDetailScreen legitimately shows its own RouteErrorScreen for
      // that (see saved_recipe_detail.dart). Routing's only guarantee here
      // is that a well-formed id isn't bounced by the format guard before
      // ever reaching the screen — unlike the malformed case above.
      expect(find.byType(MealDetailScreen), findsOneWidget);
    },
  );
}
