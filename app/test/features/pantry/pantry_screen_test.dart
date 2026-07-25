// Widget coverage for the Pantry screen: the `+` sheet's three modes from
// both empty and populated pantry (AC-PAN-03), swipe delete + undo
// (AC-UX-01/02), the AC-PAN-12 stranded-filter fix, the AC-HAP-05
// filter-chip haptic, and R-07's delete-failure guard.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';

import '../../data/fixture.dart';
import '../../support/harness.dart';

/// Forces `PantryRepository.deleteItem` to fail, so R-07's guard around
/// `deletePantryItemWithUndo` can be exercised without a real DB failure
/// mode to hand — stays trivial (override the one method under test) since
/// its only job is injecting that one specific failure.
class _ThrowingDeletePantryRepository extends PantryRepository {
  _ThrowingDeletePantryRepository(super.db, super.ingredients);

  @override
  Future<void> deleteItem({required int id, required String userId}) {
    return Future<void>.error(Exception('simulated DB failure'));
  }
}

void main() {
  group('PantryScreen', () {
    late AppTestHarness harness;
    late PantryRepository pantry;

    setUp(() {
      harness = AppTestHarness();
      pantry = PantryRepository(harness.db, IngredientsRepository(harness.db));
    });

    tearDown(() => harness.dispose());

    testWidgets('empty pantry: the + sheet offers all three intake modes '
        '(AC-PAN-03)', (WidgetTester tester) async {
      await harness.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();

      expect(find.text('Your pantry is empty'), findsOneWidget);

      await tester.tap(find.text('Add items'));
      await tester.pumpAndSettle();

      expect(find.text('Scan receipt'), findsOneWidget);
      expect(find.text('Describe purchase'), findsOneWidget);
      expect(find.text('Manual entry'), findsOneWidget);
    });

    testWidgets('populated pantry: the + sheet still offers all three modes '
        '(AC-PAN-03)', (WidgetTester tester) async {
      await pantry.addItem(
        userId: 'test-user',
        name: 'milk',
        quantity: 1,
        unit: 'l',
        category: 'dairy',
        now: DateTime(2026, 1, 1),
      );

      await harness.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.add_rounded));
      await tester.pumpAndSettle();

      expect(find.text('Scan receipt'), findsOneWidget);
      expect(find.text('Describe purchase'), findsOneWidget);
      expect(find.text('Manual entry'), findsOneWidget);
    });

    testWidgets(
      'each row settles in via GleanListEntrance rather than popping in '
      '(R-10, AC-TRN-02)',
      (WidgetTester tester) async {
        await pantry.addItem(
          userId: 'test-user',
          name: 'butter',
          quantity: 250,
          unit: 'g',
          category: 'dairy',
          now: DateTime(2026, 1, 1),
        );

        await harness.pumpAt(tester, AppRoutes.pantry.path);
        await tester.pumpAndSettle();

        expect(
          find.ancestor(
            of: find.text('butter'),
            matching: find.byType(GleanListEntrance),
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets('swipe-to-delete removes the item and shows undo; undo '
        'restores it (AC-UX-01/02)', (WidgetTester tester) async {
      await pantry.addItem(
        userId: 'test-user',
        name: 'butter',
        quantity: 250,
        unit: 'g',
        category: 'dairy',
        now: DateTime(2026, 1, 1),
      );

      await harness.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();
      expect(find.text('butter'), findsOneWidget);

      // Exactly one delete affordance: no separate trash icon anywhere.
      expect(find.byIcon(Icons.delete_outline_rounded), findsNothing);

      await tester.drag(find.text('butter'), const Offset(-600, 0));
      await tester.pumpAndSettle();

      expect(find.text('butter removed'), findsOneWidget);
      expect(find.text('Undo'), findsOneWidget);
      expect(
        await tester.runAsync(() => pantry.watchAll('test-user').first),
        isEmpty,
      );

      // A single swipe-delete commit fires exactly one haptic (AC-HAP-03 —
      // the RN app double-buzzed via row + IconButton).
      expect(harness.hapticCalls, <HapticWeight>[HapticWeight.medium]);

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(find.text('butter'), findsOneWidget);
      expect(
        await tester.runAsync(() => pantry.watchAll('test-user').first),
        hasLength(1),
      );
    });

    testWidgets('deleting the last item of a filtered category does not '
        'strand the list (AC-PAN-12)', (WidgetTester tester) async {
      await pantry.addItem(
        userId: 'test-user',
        name: 'strawberries',
        quantity: 1,
        unit: 'punnet',
        category:
            'berries', // only berries item -> its own "Veg & Fruit" section
        now: DateTime(2026, 1, 1),
      );
      await pantry.addItem(
        userId: 'test-user',
        name: 'chicken breast',
        quantity: 500,
        unit: 'g',
        category: 'poultry',
        now: DateTime(2026, 1, 1),
      );

      await harness.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();

      // Select the "Veg" filter chip (the only category the berries item is
      // in), firing the selection haptic (AC-HAP-05).
      await tester.tap(find.text('Veg · 1'));
      await tester.pumpAndSettle();
      expect(harness.hapticCalls, contains(HapticWeight.selection));
      expect(find.text('strawberries'), findsOneWidget);
      expect(find.text('chicken breast'), findsNothing);

      // Delete the only item in the selected category.
      await tester.drag(find.text('strawberries'), const Offset(-600, 0));
      await tester.pumpAndSettle();

      // The RN bug: a blank body with no chip selected. Here the view must
      // recover to a valid state — the remaining item (in a different
      // category) becomes visible again, i.e. the filter has fallen back to
      // "All" rather than matching nothing.
      expect(find.text('chicken breast'), findsOneWidget);
      expect(find.text('Nothing left to review.'), findsNothing);
    });

    testWidgets('a tap on a row opens the quantity/unit/expiry sheet '
        '(AC-PAN-07)', (WidgetTester tester) async {
      await pantry.addItem(
        userId: 'test-user',
        name: 'onion',
        quantity: 3,
        unit: 'unit',
        category: 'alliums',
        now: DateTime(2026, 1, 1),
      );

      await harness.pumpAt(tester, AppRoutes.pantry.path);
      await tester.pumpAndSettle();

      await tester.tap(find.text('onion'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(TextField, 'Quantity'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'Unit'), findsOneWidget);
      expect(find.text('Save'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);

      // Decimal input is freely typeable, and 0 fails validation.
      await tester.enterText(find.widgetWithText(TextField, 'Quantity'), '0');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Enter a quantity greater than 0'), findsOneWidget);

      await tester.enterText(find.widgetWithText(TextField, 'Quantity'), '1.5');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();

      final saved = (await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      ))!.single;
      expect(saved.quantity, 1.5);
    });

    gleanWidgetTest(
      'a delete failure is caught and surfaced, leaving the row intact '
      '(R-07)',
      (WidgetTester tester) async {
        final throwingDb = createTestDatabase();
        addTearDown(() => throwingDb.close());
        final throwingRepo = _ThrowingDeletePantryRepository(
          throwingDb,
          IngredientsRepository(throwingDb),
        );
        await throwingRepo.addItem(
          userId: 'test-user',
          name: 'butter',
          quantity: 250,
          unit: 'g',
          category: 'dairy',
          now: DateTime(2026, 1, 1),
        );

        final localHarness = AppTestHarness(
          overrides: [pantryRepositoryProvider.overrideWithValue(throwingRepo)],
        );
        addTearDown(() => localHarness.dispose());

        await localHarness.pumpAt(tester, AppRoutes.pantry.path);
        await tester.pumpAndSettle();
        expect(find.text('butter'), findsOneWidget);

        await tester.drag(find.text('butter'), const Offset(-600, 0));
        await tester.pumpAndSettle();

        // No undo snackbar — the delete failed and was caught, not
        // propagated uncaught with zero feedback (the R-07 bug).
        expect(find.text('Undo'), findsNothing);
        expect(find.textContaining('Could not remove'), findsOneWidget);

        // The row must survive untouched in the data layer.
        final survivors = await tester.runAsync(
          () => throwingRepo.watchAll('test-user').first,
        );
        expect(survivors!.single.canonicalName, 'butter');
      },
    );
  });
}
