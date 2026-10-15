// R-08: `SignedOutBanner` and `aiFeaturesAvailableProvider` used to be
// referenced only by their own test — nothing in the assembled app mounted
// the banner or gated an AI-backed action on the provider. This suite pumps
// the *real* app (`AppShell` + the real feature screens, via
// `AppTestHarness`) rather than injecting either directly, so it fails if
// the wiring is ever removed again.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/auth_state.dart';

import '../../support/harness.dart';

void main() {
  group('R-08: expired session shows the banner and gates AI features', () {
    late AppTestHarness harness;
    late PantryRepository pantry;

    setUp(() {
      harness = AppTestHarness();
      pantry = PantryRepository(harness.db, IngredientsRepository(harness.db));
    });

    tearDown(() => harness.dispose());

    testWidgets(
      'the banner is mounted in the assembled shell, and local reads keep '
      'working underneath it',
      (WidgetTester tester) async {
        await pantry.addItem(
          userId: harness.userId,
          name: 'Milk',
          quantity: 1,
          unit: 'l',
          category: 'dairy',
        );

        await harness.pumpAt(tester, AppRoutes.pantry.path);
        await tester.pumpAndSettle();

        // Nothing shown while the session is active (the harness default).
        expect(find.textContaining('Signed out'), findsNothing);
        // `IngredientsRepository.resolveOrCreate` lower-cases the resolved
        // canonical name (see `plan_rows_test.dart`'s equivalent note).
        expect(find.textContaining('milk'), findsOneWidget);

        harness.container
            .read(authStatusProvider.notifier)
            .setStatus(AuthStatus.expired);
        await tester.pumpAndSettle();

        // The banner is now visible from the shell, not from Pantry itself...
        expect(find.textContaining('Signed out'), findsOneWidget);
        // ...and the local read underneath it is completely unaffected —
        // this is the entire point of AC-AUTH-04's decision (§5): expiry
        // must never gate a local read, only an AI-backed action.
        expect(find.textContaining('milk'), findsOneWidget);
      },
    );

    testWidgets(
      'Pantry: Scan receipt and Describe purchase are disabled, Manual '
      'entry stays usable',
      (WidgetTester tester) async {
        await harness.pumpAt(tester, AppRoutes.pantry.path);
        await tester.pumpAndSettle();
        harness.container
            .read(authStatusProvider.notifier)
            .setStatus(AuthStatus.expired);
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.add_rounded));
        await tester.pumpAndSettle();

        final ListTile scanTile = tester.widget<ListTile>(
          find.widgetWithText(ListTile, 'Scan receipt'),
        );
        final ListTile describeTile = tester.widget<ListTile>(
          find.widgetWithText(ListTile, 'Describe purchase'),
        );
        final ListTile manualTile = tester.widget<ListTile>(
          find.widgetWithText(ListTile, 'Manual entry'),
        );
        expect(scanTile.enabled, isFalse);
        expect(describeTile.enabled, isFalse);
        expect(manualTile.enabled, isTrue);

        // Tapping a disabled tile must not navigate anywhere.
        await tester.tap(find.widgetWithText(ListTile, 'Scan receipt'));
        await tester.pumpAndSettle();
        expect(find.widgetWithText(ListTile, 'Scan receipt'), findsOneWidget);
      },
    );

    testWidgets('Plan: the Generate button is disabled', (
      WidgetTester tester,
    ) async {
      await harness.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      harness.container
          .read(authStatusProvider.notifier)
          .setStatus(AuthStatus.expired);
      await tester.pumpAndSettle();

      final FilledButton generate = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Generate'),
      );
      expect(generate.onPressed, isNull);
    });

    testWidgets('Shop: Describe list is disabled', (WidgetTester tester) async {
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      harness.container
          .read(authStatusProvider.notifier)
          .setStatus(AuthStatus.expired);
      await tester.pumpAndSettle();

      final IconButton describeButton = tester.widget<IconButton>(
        find.widgetWithIcon(IconButton, Icons.auto_awesome_rounded),
      );
      expect(describeButton.onPressed, isNull);
    });

    testWidgets(
      'Meals: search is disabled and explains why, import is disabled',
      (WidgetTester tester) async {
        await harness.pumpAt(tester, AppRoutes.meals.path);
        await tester.pumpAndSettle();
        harness.container
            .read(authStatusProvider.notifier)
            .setStatus(AuthStatus.expired);
        await tester.pumpAndSettle();

        await tester.tap(find.text('Search'));
        await tester.pumpAndSettle();

        final TextField searchField = tester.widget<TextField>(
          find.byType(TextField),
        );
        expect(searchField.enabled, isFalse);

        final IconButton importButton = tester.widget<IconButton>(
          find.widgetWithIcon(IconButton, Icons.link_rounded),
        );
        expect(importButton.onPressed, isNull);

        expect(find.text('Sign in to search recipes'), findsOneWidget);
      },
    );
  });
}
