// AC-TEST-06 (non-negotiable, per IMPLEMENTATION.md) and the checkout half
// of AC-SHOP-01/02/03: a receipt only removes the rows it actually
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
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('Shop checkout', () {
    late AppTestHarness harness;
    late ShoppingRepository shopping;
    late IngredientsRepository ingredients;

    setUp(() {
      harness = AppTestHarness();
      ingredients = IngredientsRepository(harness.db);
      shopping = ShoppingRepository(harness.db, ingredients);
    });

    tearDown(() => harness.dispose());

    testWidgets(
      'a receipt resolving 4 of 12 checked rows removes exactly those 4 and '
      'leaves 8 (AC-SHOP-01, AC-TEST-06)',
      (WidgetTester tester) async {
        final List<int> ingredientIds = <int>[];
        for (int i = 0; i < 12; i++) {
          final int id = await shopping.addManualItem(
            userId: 'test-user',
            name: 'Item $i',
          );
          // A plain one-shot lookup (not `.watchAll(...).first`) — same
          // ingredient, same id `addManualItem` just resolved, since
          // `resolveOrCreate` is idempotent by name. Avoids subscribing to
          // and cancelling a drift stream twelve times over in a loop.
          final ingredient = await ingredients.resolveOrCreate(
            canonicalName: 'Item $i',
          );
          ingredientIds.add(ingredient.id);
          await shopping.toggleItem(id: id, userId: 'test-user', checked: true);
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

        final int removedCount = await shopping.resolveCheckout(
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
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          hasLength(8),
        );
      },
    );

    testWidgets(
      '"Done shopping" completes a receipt-less trip, leaving unchecked rows '
      '(AC-SHOP-02)',
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

        await tester.tap(find.text('Done shopping'));
        await tester.pumpAndSettle();

        expect(find.text('Bananas'), findsOneWidget);
        expect(find.text('Milk'), findsNothing);
        expect(find.text('1 item checked off'), findsOneWidget);
        expect(
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          hasLength(1),
        );

        await tester.tap(find.text('Undo'));
        await tester.pumpAndSettle();

        expect(find.text('Milk'), findsOneWidget);
        expect(
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          hasLength(2),
        );
      },
    );

    testWidgets(
      'a manual item resolves a real ingredient identity and can later match '
      'a receipt (AC-SHOP-03)',
      (WidgetTester tester) async {
        final int id = await shopping.addManualItem(
          userId: 'test-user',
          name: 'Oats',
        );
        // A plain one-shot lookup, not `.watchAll(...).first` — see the
        // comment on the same pattern above.
        final ingredient = await ingredients.resolveOrCreate(
          canonicalName: 'Oats',
        );
        // `ShoppingListItemView.ingredientId` is a non-nullable `int` — the
        // schema and the view model make "null" structurally impossible
        // here, unlike RN's `ingredient_id: null`. Assert it resolved to a
        // real row rather than some sentinel.
        expect(ingredient.id, greaterThan(0));

        await shopping.toggleItem(id: id, userId: 'test-user', checked: true);

        final int removed = await shopping.resolveCheckout(
          userId: 'test-user',
          resolvedIngredientIds: <int>[ingredient.id],
        );

        expect(removed, 1);
        expect(
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          isEmpty,
        );
      },
    );
  });
}
