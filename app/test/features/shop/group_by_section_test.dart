// The Shopping tab's "Group by section" toggle: non-empty store sections in the fixed order with the To buy /
// In cart split kept inside each, the flat list restored exactly when off, and the choice remembered.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('Shop "Group by section"', () {
    late AppTestHarness harness;

    ShoppingRepository shopping() =>
        harness.container.read(shoppingRepositoryProvider);

    // Dairy first, flour second, apples last: the opposite of store order, so the grouped order can only
    // come from the sections.
    Future<void> seedList() async {
      await shopping().addAiItems(
        userId: 'test-user',
        items: const <AiShoppingItem>[
          AiShoppingItem(
            name: 'Milk',
            quantity: 1,
            unit: 'l',
            category: 'dairy',
          ),
        ],
      );
      await shopping().addManualItem(userId: 'test-user', name: 'Plain flour');
      await shopping().addAiItems(
        userId: 'test-user',
        items: const <AiShoppingItem>[
          AiShoppingItem(
            name: 'Pears',
            quantity: 2,
            unit: 'x',
            category: 'stone_fruit',
          ),
          AiShoppingItem(
            name: 'Apples',
            quantity: 4,
            unit: 'x',
            category: 'citrus',
          ),
        ],
      );
      final items = await shopping().watchAll('test-user').first;
      await shopping().toggleRows(
        ids: <int>[items.firstWhere((i) => i.name == 'Pears').id],
        userId: 'test-user',
        checked: true,
      );
    }

    double top(WidgetTester tester, String text) =>
        tester.getTopLeft(find.textContaining(text)).dy;

    // Tall enough that every row is built, so the rows' positions can be compared.
    void useTallScreen(WidgetTester tester) {
      tester.view.physicalSize = const Size(800, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    setUp(() => harness = AppTestHarness());

    tearDown(() => harness.dispose());

    testWidgets('on: only non-empty sections show, in store order, with '
        'To buy rows above In cart rows inside each', (tester) async {
      useTallScreen(tester);
      await tester.runAsync(seedList);
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Group by section'));
      await tester.pumpAndSettle();

      expect(find.text('FRUIT & VEG'), findsOneWidget);
      expect(find.text('DAIRY, EGGS & CHILLED'), findsOneWidget);
      expect(find.text('BAKING'), findsOneWidget);
      expect(find.text('MEAT & FISH'), findsNothing);
      expect(find.text('OTHER'), findsNothing);
      expect(find.text('TO BUY'), findsNothing);
      expect(find.text('IN CART'), findsNothing);
      final List<double> order = <double>[
        top(tester, 'FRUIT & VEG'),
        top(tester, 'Apples'),
        top(tester, 'Pears'),
        top(tester, 'DAIRY, EGGS & CHILLED'),
        top(tester, 'Milk'),
        top(tester, 'BAKING'),
        top(tester, 'Plain flour'),
      ];
      expect(order, orderedEquals(<double>[...order]..sort()));
    });

    testWidgets('off again: the flat To buy / In cart list is restored '
        'exactly', (tester) async {
      useTallScreen(tester);
      await tester.runAsync(seedList);
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      final List<double> flat = <double>[
        top(tester, 'TO BUY'),
        top(tester, 'Apples'),
        top(tester, 'Plain flour'),
        top(tester, 'Milk'),
        top(tester, 'IN CART'),
        top(tester, 'Pears'),
      ];

      await tester.tap(find.byTooltip('Group by section'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Group by section'));
      await tester.pumpAndSettle();

      expect(find.text('FRUIT & VEG'), findsNothing);
      expect(<double>[
        top(tester, 'TO BUY'),
        top(tester, 'Apples'),
        top(tester, 'Plain flour'),
        top(tester, 'Milk'),
        top(tester, 'IN CART'),
        top(tester, 'Pears'),
      ], flat);
    });

    testWidgets('the choice is remembered: a fresh screen opens grouped '
        'once it was turned on', (tester) async {
      useTallScreen(tester);
      await tester.runAsync(seedList);
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Group by section'));
      await tester.pumpAndSettle();

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(milliseconds: 1));
      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      expect(find.text('FRUIT & VEG'), findsOneWidget);
    });
  });
}
