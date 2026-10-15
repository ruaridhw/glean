// Checkout: a receipt only removes the rows it actually
// resolved, "Done shopping" completes a receipt-less trip with undo, and a
// manual item's resolved ingredient identity lets it participate in a
// receipt match at all.
//
// The mutation this proves (`ShoppingRepository.resolveCheckout`) is called
// by the shared intake review screen (owned by the Pantry+Intake wave) when
// `ReviewArgs.returnToShop` is true, not by anything in this module. This
// test calls it directly — exactly what that screen will do — and asserts
// on `ShopScreen`'s own rendering, which is the "UI half" this wave owns:
// proof that the Shop tab's list correctly reflects the data layer's
// data-preserving behaviour, live, with no `ref.invalidate` anywhere.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('Shop checkout', () {
    late AppTestHarness harness;

    // Read lazily: touching `harness.container` in `setUp` would start drift
    // work outside the test's fake-async zone.
    ShoppingRepository shopping() =>
        harness.container.read(shoppingRepositoryProvider);
    PantryRepository pantry() =>
        harness.container.read(pantryRepositoryProvider);
    IngredientsRepository ingredients() =>
        harness.container.read(ingredientsRepositoryProvider);

    setUp(() => harness = AppTestHarness());

    tearDown(() => harness.dispose());

    testWidgets(
      'a receipt resolving 4 of 12 checked rows removes exactly those 4 and '
      'leaves 8',
      (WidgetTester tester) async {
        final List<int> ingredientIds = <int>[];
        for (int i = 0; i < 12; i++) {
          final int id = await shopping().addManualItem(
            userId: 'test-user',
            name: 'Item $i',
          );
          // A plain one-shot lookup (not `.watchAll(...).first`) — same
          // ingredient, same id `addManualItem` just resolved, since
          // `resolveOrCreate` is idempotent by name. Avoids subscribing to
          // and cancelling a drift stream twelve times over in a loop.
          final ingredient = await ingredients().resolveOrCreate(
            canonicalName: 'Item $i',
          );
          ingredientIds.add(ingredient.id);
          await shopping().toggleRows(
            ids: [id],
            userId: 'test-user',
            checked: true,
          );
        }
        final List<int> resolved = ingredientIds.sublist(0, 4);

        // All 12 rows are checked, so they'd otherwise overflow the default
        // test-surface viewport and `ListView` (correctly) never mounts the
        // off-screen ones — `find.text` can only see mounted Elements. A
        // taller surface lets every row assert without a scroll gesture per
        // item.
        addTearDown(tester.view.resetPhysicalSize);
        tester.view.physicalSize = const Size(1080, 3600);

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();
        for (int i = 0; i < 12; i++) {
          expect(find.text('Item $i'), findsOneWidget);
        }

        final int removedCount = await shopping().resolveCheckout(
          userId: 'test-user',
          resolvedIngredientIds: resolved,
        );
        expect(removedCount, 4);
        await tester.pumpAndSettle();

        for (int i = 0; i < 4; i++) {
          expect(find.text('Item $i'), findsNothing);
        }
        for (int i = 4; i < 12; i++) {
          expect(find.text('Item $i'), findsOneWidget);
        }
        expect(
          await tester.runAsync(() => shopping().watchAll('test-user').first),
          hasLength(8),
        );
      },
    );

    testWidgets(
      '"Done shopping" opens the review with the checked Shopping items; '
      'confirming stocks the pantry with the list quantities and clears '
      'only the checked rows',
      (WidgetTester tester) async {
        await shopping().addManualItem(userId: 'test-user', name: 'Bananas');
        final int milkId = await shopping().addManualItem(
          userId: 'test-user',
          name: 'Milk',
          quantity: 500,
          unit: 'ml',
        );
        final int eggsId = await shopping().addManualItem(
          userId: 'test-user',
          name: 'Eggs',
          quantity: 6,
          unit: 'units',
        );
        await shopping().toggleRows(
          ids: [milkId, eggsId],
          userId: 'test-user',
          checked: true,
        );

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Done shopping'));
        await tester.pumpAndSettle();

        expect(find.text('Review items'), findsOneWidget);
        expect(find.widgetWithText(TextField, 'Milk'), findsOneWidget);
        expect(find.widgetWithText(TextField, 'Eggs'), findsOneWidget);
        expect(find.widgetWithText(TextField, '500'), findsOneWidget);
        expect(find.widgetWithText(TextField, '6'), findsOneWidget);
        expect(find.text('Bananas'), findsNothing);

        await tester.tap(find.text('Add 2 items'));
        await tester.pumpAndSettle();

        final pantryItems = (await tester.runAsync(
          () => pantry().getAll('test-user'),
        ))!;
        expect(
          {for (final item in pantryItems) item.canonicalName: item.quantity},
          {'milk': 500.0, 'eggs': 6.0},
        );
        expect(find.text('Bananas'), findsOneWidget);
        expect(find.text('Milk'), findsNothing);
        expect(find.text('Eggs'), findsNothing);
      },
    );

    testWidgets('cancelling the review leaves the checked Shopping items '
        'checked and the pantry empty', (WidgetTester tester) async {
      final int milkId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
      );
      await shopping().toggleRows(
        ids: [milkId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done shopping'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Review items'), findsNothing);
      expect(find.text('Milk'), findsOneWidget);
      final rows = (await tester.runAsync(
        () => shopping().watchAll('test-user').first,
      ))!;
      expect(rows.single.isChecked, isTrue);
      expect(
        await tester.runAsync(() => pantry().getAll('test-user')),
        isEmpty,
      );
    });

    testWidgets('one Undo after confirming restores the checked Shopping items '
        'and reverses the pantry additions exactly', (
      WidgetTester tester,
    ) async {
      await pantry().addItem(
        userId: 'test-user',
        name: 'eggs',
        quantity: 4,
        unit: 'units',
        category: 'dairy',
      );
      final int milkId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
        quantity: 500,
        unit: 'ml',
      );
      final int eggsId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Eggs',
        quantity: 6,
        unit: 'units',
      );
      await shopping().toggleRows(
        ids: [milkId, eggsId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done shopping'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add 2 items'));
      await tester.pumpAndSettle();

      expect(find.text('Added 2 items to your pantry'), findsOneWidget);
      final stocked = (await tester.runAsync(
        () => pantry().getAll('test-user'),
      ))!;
      expect(
        {for (final i in stocked) i.canonicalName: i.quantity},
        {'eggs': 10.0, 'milk': 500.0},
      );

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      final restored = (await tester.runAsync(
        () => shopping().watchAll('test-user').first,
      ))!;
      expect(restored.map((r) => r.name), unorderedEquals(['Milk', 'Eggs']));
      expect(restored.every((r) => r.isChecked), isTrue);
      final afterUndo = (await tester.runAsync(
        () => pantry().getAll('test-user'),
      ))!;
      expect(
        {for (final i in afterUndo) i.canonicalName: i.quantity},
        {'eggs': 4.0},
      );
    });

    testWidgets('a checked Shopping item arrives with its ingredient\'s '
        'category, and one without a category confirms uncategorised', (
      WidgetTester tester,
    ) async {
      await ingredients().resolveOrCreate(
        canonicalName: 'milk',
        category: 'dairy',
      );
      final int milkId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
      );
      final int plumsId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Plan plums',
      );
      await shopping().toggleRows(
        ids: [milkId, plumsId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done shopping'));
      await tester.pumpAndSettle();

      // Only the row with no category asks for one.
      expect(
        find.text("Optional: we couldn't identify a category for this item."),
        findsOneWidget,
      );
      await tester.tap(find.text('Add 2 items'));
      await tester.pumpAndSettle();

      final stocked = (await tester.runAsync(
        () => pantry().getAll('test-user'),
      ))!;
      expect(
        {for (final i in stocked) i.canonicalName: i.category},
        {'milk': 'dairy', 'plan plums': null},
      );
    });

    testWidgets('the checkout bar says checked items go to the pantry, not '
        'that finishing does nothing', (WidgetTester tester) async {
      final int milkId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
      );
      await shopping().toggleRows(
        ids: [milkId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      expect(
        find.text('Add them to your pantry, or scan a receipt'),
        findsOneWidget,
      );
      expect(find.textContaining('finish without'), findsNothing);
    });

    testWidgets('removing one of two checked rows for the same item in the '
        'review clears only the other, and Undo restores exactly it', (
      WidgetTester tester,
    ) async {
      final int firstId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
        quantity: 500,
        unit: 'ml',
      );
      final int secondId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Milk',
        quantity: 250,
        unit: 'ml',
      );
      await shopping().toggleRows(
        ids: [firstId, secondId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done shopping'));
      await tester.pumpAndSettle();
      // Rows list newest first: drop the 500 ml one.
      final removeButtons = find.byTooltip('Remove');
      expect(removeButtons, findsNWidgets(2));
      final Finder fiveHundred = find.widgetWithText(TextField, '500');
      final int rowIndex = tester
          .widgetList<TextField>(find.byType(TextField))
          .toList()
          .indexWhere((f) => f.controller?.text == '500');
      expect(rowIndex, greaterThanOrEqualTo(0));
      expect(fiveHundred, findsOneWidget);
      // Each row owns one name, qty and unit field plus a Remove button.
      await tester.tap(removeButtons.at(rowIndex ~/ 3));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final ids = (await tester.runAsync(
        () => shopping().watchAll('test-user').first,
      ))!.map((r) => r.id);
      expect(ids, [firstId]);
      expect(
        (await tester.runAsync(
          () => pantry().getAll('test-user'),
        ))!.single.quantity,
        250.0,
      );

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      final restored = (await tester.runAsync(
        () => shopping().watchAll('test-user').first,
      ))!;
      expect(restored.map((r) => r.id), unorderedEquals([firstId, secondId]));
      expect(restored.every((r) => r.isChecked), isTrue);
      expect(
        await tester.runAsync(() => pantry().getAll('test-user')),
        isEmpty,
      );
    });

    testWidgets('renaming a row in the review still clears the checked '
        'Shopping item it came from', (WidgetTester tester) async {
      final int oatId = await shopping().addManualItem(
        userId: 'test-user',
        name: 'Oat milk',
      );
      await shopping().toggleRows(
        ids: [oatId],
        userId: 'test-user',
        checked: true,
      );

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Done shopping'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Oat milk'),
        'Almond milk',
      );
      await tester.pump();
      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      expect(
        await tester.runAsync(() => shopping().watchAll('test-user').first),
        isEmpty,
      );
      expect(
        (await tester.runAsync(
          () => pantry().getAll('test-user'),
        ))!.single.canonicalName,
        'almond milk',
      );

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      final restored = (await tester.runAsync(
        () => shopping().watchAll('test-user').first,
      ))!;
      expect(restored.single.name, 'Oat milk');
      expect(restored.single.isChecked, isTrue);
    });
  });
}
