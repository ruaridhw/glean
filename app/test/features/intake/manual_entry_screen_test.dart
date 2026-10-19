// Widget coverage for manual pantry entry — dead code in the RN app;
// reachable here from the `+` sheet. The one intake surface with
// no LLM classification behind it, so it must ask for an ingredient group directly;
// that's what lets expiry inference fire at all for a manually-added item.
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

    testWidgets(
      'requires a name, a valid quantity and an ingredient group before '
      'saving',
      (WidgetTester tester) async {
        await pumpManualEntry(tester);

        await tester.tap(find.text('Add to pantry'));
        await tester.pump();

        expect(find.text('Enter a quantity greater than 0'), findsOneWidget);
        expect(find.text('Choose an ingredient group'), findsOneWidget);
        expect(
          await tester.runAsync(() => pantry.watchAll('test-user').first),
          isEmpty,
        );
      },
    );

    testWidgets('saving a valid item infers an expiry from the chosen '
        'ingredient group and returns to Pantry', (WidgetTester tester) async {
      await pumpManualEntry(tester);

      await tester.enterText(
        find.widgetWithText(TextField, 'Ingredient name'),
        'kale',
      );
      await tester.enterText(find.widgetWithText(TextField, 'Quantity'), '2');

      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Leafy greens & salad').last);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add to pantry'));
      await tester.pumpAndSettle();

      // The mediumImpact data-commit haptic fires.
      expect(harness.hapticCalls, contains(HapticWeight.medium));

      final saved = (await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      ))!.single;
      expect(saved.canonicalName, 'kale');
      expect(saved.quantity, 2);
      expect(saved.groupId, 'leafy_greens');
      expect(saved.expiryDate, isNotNull);

      // The modal task exits back to Pantry, which now shows the new item.
      expect(find.byType(ManualEntryScreen), findsNothing);
      expect(find.text('kale'), findsOneWidget);
    });

    testWidgets(
      'a unit mismatch shows a targeted message, not the generic "try '
      'again"',
      (WidgetTester tester) async {
        // Establishes 'units' as chives' canonical/row unit.
        await pantry.addItem(
          userId: 'test-user',
          name: 'chives',
          quantity: 3,
          unit: 'units',
          groupId: 'onions_and_garlic',
        );

        await pumpManualEntry(tester);

        await tester.enterText(
          find.widgetWithText(TextField, 'Ingredient name'),
          'chives',
        );
        await tester.enterText(
          find.widgetWithText(TextField, 'Quantity'),
          '10',
        );
        // 'g' is the default chip selection — no conversion path to the
        // existing row's 'units'.
        await tester.tap(find.byType(DropdownButtonFormField<String>));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Onions & garlic').last);
        await tester.pumpAndSettle();

        await tester.tap(find.text('Add to pantry'));
        await tester.pumpAndSettle();

        expect(
          find.textContaining('chives is stocked in units'),
          findsOneWidget,
        );
        expect(find.text('Could not save this item. Try again.'), findsNothing);
        // Still on this screen — the row was not committed.
        expect(find.byType(ManualEntryScreen), findsOneWidget);
      },
    );
  });
}
