// Widget coverage for the Shop tab's main list: empty state, grouped
// sections with the unified cart wording (AC-SHOP-07), tap-to-toggle,
// swipe-to-delete + undo (AC-UX-01/02), and the pinned add field staying put
// with a long list and with the keyboard up (AC-SHOP-08/10).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('ShopScreen', () {
    late AppTestHarness harness;
    late ShoppingRepository shopping;

    setUp(() {
      harness = AppTestHarness();
      shopping = ShoppingRepository(
        harness.db,
        IngredientsRepository(harness.db),
      );
    });

    tearDown(() => harness.dispose());

    testWidgets('shows the empty state with no shopping list items', (
      WidgetTester tester,
    ) async {
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      expect(find.text('Your shopping list is empty'), findsOneWidget);
    });

    testWidgets(
      'lists items into "To buy"/"In cart" with one wording for the count '
      '(AC-SHOP-07)',
      (WidgetTester tester) async {
        await shopping.addManualItem(userId: 'test-user', name: 'Bananas');
        final int milkId = await shopping.addManualItem(
          userId: 'test-user',
          name: 'Milk',
        );
        await shopping.toggleItem(
          id: milkId,
          userId: 'test-user',
          checked: true,
        );

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.text('Bananas'), findsOneWidget);
        expect(find.text('Milk'), findsOneWidget);
        // Section headers render uppercase (FINDINGS.md F-04 — Flutter has
        // no `text-transform`, so the widget calls `.toUpperCase()` itself).
        expect(find.text('TO BUY'), findsOneWidget);
        expect(find.text('IN CART'), findsOneWidget);
        // The chip row, the checkout bar and the section header all agree on
        // one phrase for this count — never "N checked" anywhere.
        expect(find.textContaining('1 item in cart'), findsWidgets);
        expect(find.textContaining('1 item to buy'), findsOneWidget);
        expect(find.text('N checked'), findsNothing);
      },
    );

    testWidgets('tapping a row toggles it checked with a light haptic', (
      WidgetTester tester,
    ) async {
      await shopping.addManualItem(userId: 'test-user', name: 'Bananas');

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Bananas'));
      await tester.pumpAndSettle();

      expect(harness.hapticCalls, contains(HapticWeight.light));
      final items = await tester.runAsync(
        () => shopping.watchAll('test-user').first,
      );
      expect(items!.single.isChecked, isTrue);
    });

    testWidgets('swipe-to-delete removes a row with undo (AC-UX-01/02)', (
      WidgetTester tester,
    ) async {
      await shopping.addManualItem(userId: 'test-user', name: 'Bananas');

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      await tester.drag(find.text('Bananas'), const Offset(-600, 0));
      await tester.pumpAndSettle();

      expect(find.text('Bananas removed'), findsOneWidget);
      expect(find.text('Undo'), findsOneWidget);
      expect(
        await tester.runAsync(() => shopping.watchAll('test-user').first),
        isEmpty,
      );
      // SwipeToDeleteRow fires exactly one haptic for the commit — the
      // undo snackbar itself must not add a second (AC-HAP-03).
      expect(
        harness.hapticCalls.where((w) => w == HapticWeight.medium),
        hasLength(1),
      );

      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      expect(
        await tester.runAsync(() => shopping.watchAll('test-user').first),
        hasLength(1),
      );
      expect(find.text('Bananas'), findsOneWidget);
    });

    testWidgets(
      'the pinned add field stays visible with a long list (AC-SHOP-08)',
      (WidgetTester tester) async {
        for (int i = 0; i < 30; i++) {
          await shopping.addManualItem(userId: 'test-user', name: 'Item $i');
        }

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.byType(TextField), findsOneWidget);
        await tester.drag(find.byType(ListView), const Offset(0, -2000));
        await tester.pump();

        // Still there after scrolling the *list* — it was never part of the
        // scrollable, unlike RN's `SectionList` header.
        expect(find.byType(TextField), findsOneWidget);
        await tester.enterText(find.byType(TextField), 'Late addition');
        await tester.pump();
        await tester.tap(find.byIcon(Icons.add_rounded));
        await tester.pumpAndSettle();

        expect(
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          hasLength(31),
        );
      },
    );

    testWidgets('the pinned add field is not covered when the keyboard is up '
        '(AC-SHOP-10)', (WidgetTester tester) async {
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      addTearDown(tester.view.resetViewInsets);
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      await tester.pumpAndSettle();

      // `Scaffold.resizeToAvoidBottomInset` (the default, set explicitly
      // in `ShopScreen`) shrinks the body instead of letting the keyboard
      // overlap it, so the field stays on-screen and above the inset.
      final double fieldBottom = tester
          .getBottomLeft(find.byType(TextField))
          .dy;
      final double screenHeight =
          tester.view.physicalSize.height / tester.view.devicePixelRatio;
      expect(fieldBottom, lessThan(screenHeight - 300));
    });
  });
}
