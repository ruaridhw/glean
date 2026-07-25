// Widget coverage for manual pantry entry — dead code in the RN app;
// reachable here from the `+` sheet (AC-PAN-03). The one intake surface with
// no LLM classification behind it, so it must ask for a category directly
// (FINDINGS.md F-07/F-08) — that's what lets expiry inference fire at all
// for a manually-added item (AC-PAN-01).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/intake/manual_entry_screen.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('ManualEntryScreen', () {
    late AppTestHarness harness;
    late PantryRepository pantry;

    setUp(() {
      harness = AppTestHarness();
      pantry = PantryRepository(harness.db, IngredientsRepository(harness.db));
    });

    tearDown(() => harness.dispose());

    Future<void> pumpManualEntry(WidgetTester tester) async {
      unawaited(harness.router.pushNamed(AppRoutes.intakeManualEntry.name));
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();
    }

    testWidgets('requires a name, a valid quantity and a category before '
        'saving', (WidgetTester tester) async {
      await pumpManualEntry(tester);

      await tester.tap(find.text('Add to pantry'));
      await tester.pump();

      expect(find.text('Enter a quantity greater than 0'), findsOneWidget);
      expect(find.text('Choose a category'), findsOneWidget);
      expect(
        await tester.runAsync(() => pantry.watchAll('test-user').first),
        isEmpty,
      );
    });

    testWidgets('saving a valid item infers an expiry from the chosen '
        'category (AC-PAN-01) and returns to Pantry', (
      WidgetTester tester,
    ) async {
      await pumpManualEntry(tester);

      await tester.enterText(
        find.widgetWithText(TextField, 'Ingredient name'),
        'kale',
      );
      await tester.enterText(find.widgetWithText(TextField, 'Quantity'), '2');

      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Leafy Greens').last);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to pantry'));
      await tester.pumpAndSettle();

      // The mediumImpact data-commit haptic fires (AC-HAP-05).
      expect(harness.hapticCalls, contains(HapticWeight.medium));

      final saved = (await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      ))!.single;
      expect(saved.canonicalName, 'kale');
      expect(saved.quantity, 2);
      expect(saved.category, 'leafy_greens');
      expect(saved.expiryDate, isNotNull);

      // The modal task exits back to Pantry, which now shows the new item.
      expect(find.byType(ManualEntryScreen), findsNothing);
      expect(find.text('kale'), findsOneWidget);
    });
  });
}
