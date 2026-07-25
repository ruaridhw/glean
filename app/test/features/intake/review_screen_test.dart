// Widget coverage for the shared intake review screen (AC-PAN-05): decimal
// quantities round-trip (AC-PAN-08), zero/NaN is rejected (AC-PAN-09), the
// commit is atomic and a retry can't double (AC-PAN-10), a pantry-only
// review never touches the shopping list (AC-PAN-11), and a null-category
// pantry row requires a category pick before it can be confirmed
// (FINDINGS.md F-07/F-08).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';

import '../../support/harness.dart';

void main() {
  group('ReviewScreen', () {
    late AppTestHarness harness;
    late PantryRepository pantry;
    late ShoppingRepository shopping;

    setUp(() {
      harness = AppTestHarness();
      final ingredients = IngredientsRepository(harness.db);
      pantry = PantryRepository(harness.db, ingredients);
      shopping = ShoppingRepository(harness.db, ingredients);
    });

    tearDown(() => harness.dispose());

    Future<void> pumpReview(WidgetTester tester, ReviewArgs args) async {
      unawaited(
        harness.router.pushNamed(AppRoutes.intakeReview.name, extra: args),
      );
      await tester.pumpWidget(harness.app());
      await tester.pumpAndSettle();
    }

    testWidgets('decimal quantities are typeable and round-trip (AC-PAN-08)', (
      WidgetTester tester,
    ) async {
      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'olive oil',
              quantity: 1,
              unit: 'l',
              confidence: 0.9,
              category: 'oils_fats',
            ),
          ],
        ),
      );

      final qtyField = find.widgetWithText(TextField, 'Qty');
      await tester.enterText(qtyField, '1.5');
      await tester.pump();

      // The field still reads exactly what was typed — no `String(quantity)`
      // round-trip snapping it back to an integer.
      expect(find.text('1.5'), findsOneWidget);

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final saved = (await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      ))!.single;
      expect(saved.quantity, 1.5);
    });

    testWidgets('zero/NaN quantities fail validation — Confirm cannot write '
        '0 units (AC-PAN-09)', (WidgetTester tester) async {
      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'flour',
              quantity: 1,
              unit: 'kg',
              confidence: 0.9,
              category: 'grains',
            ),
          ],
        ),
      );

      final qtyField = find.widgetWithText(TextField, 'Qty');

      await tester.enterText(qtyField, '0');
      await tester.pump();
      expect(find.text('Enter a quantity greater than 0'), findsOneWidget);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );

      await tester.enterText(qtyField, 'abc');
      await tester.pump();
      expect(find.text('Enter a quantity greater than 0'), findsOneWidget);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );

      // Fixing it re-enables Confirm — no fallback substitution ever wrote a
      // number, it simply stayed blocked until corrected.
      await tester.enterText(qtyField, '2');
      await tester.pump();
      expect(find.text('Enter a quantity greater than 0'), findsNothing);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull,
      );
    });

    testWidgets('save is atomic: a mid-batch failure persists nothing, and '
        'retrying does not double (AC-PAN-10)', (WidgetTester tester) async {
      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'good',
              name: 'onion',
              quantity: 3,
              unit: 'unit',
              confidence: 0.9,
              category: 'alliums',
            ),
            ReviewItemDraft(
              reviewId: 'bad',
              name: 'mystery item',
              quantity: 1,
              unit: 'unit',
              confidence: 0.9,
              category: 'not_a_real_category', // rejected by the taxonomy FK
            ),
          ],
        ),
      );

      await tester.tap(find.text('Add 2 items'));
      await tester.pumpAndSettle();

      expect(find.text('Could not save. Please try again.'), findsOneWidget);
      expect(
        await tester.runAsync(() => pantry.watchAll('test-user').first),
        isEmpty,
      );
      // Still on the review screen — nothing navigated away on failure.
      expect(find.text('onion'), findsOneWidget);

      // Let the error snackbar clear before continuing — it's still
      // covering the Confirm button otherwise.
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();

      // Fix the bad row by removing it, then retry.
      await tester.tap(find.byIcon(Icons.close_rounded).last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final items = await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      );
      expect(items, hasLength(1));
      // Not doubled: exactly the one committed batch's quantity.
      expect(items!.single.quantity, 3);
    });

    testWidgets('a pantry-only review never touches the shopping list '
        '(AC-PAN-11)', (WidgetTester tester) async {
      await shopping.addManualItem(
        userId: 'test-user',
        name: 'bread',
        quantity: 1,
        unit: 'loaf',
      );
      final before = await tester.runAsync(
        () => shopping.watchAll('test-user').first,
      );

      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'butter',
              quantity: 250,
              unit: 'g',
              confidence: 0.9,
              category: 'dairy',
            ),
          ],
        ),
      );

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final after = await tester.runAsync(
        () => shopping.watchAll('test-user').first,
      );
      expect(after, hasLength(before!.length));
      expect(after!.single.name, 'bread');
    });

    testWidgets('a null-category pantry row requires a category pick before '
        'it can be confirmed (F-07/F-08)', (WidgetTester tester) async {
      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'mystery vegetable',
              quantity: 1,
              unit: 'unit',
              confidence: 0.5,
              category: null,
            ),
          ],
        ),
      );

      expect(
        find.text("We couldn't identify a category for this item."),
        findsOneWidget,
      );
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );

      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Leafy Greens').last);
      await tester.pumpAndSettle();

      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull,
      );

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final saved = (await tester.runAsync(
        () => pantry.watchAll('test-user').first,
      ))!.single;
      expect(saved.category, 'leafy_greens');
      // Expiry inference fired now that a category exists.
      expect(saved.expiryDate, isNotNull);
    });

    testWidgets('shop destination never requires a category, and persists a '
        'null one through fine', (WidgetTester tester) async {
      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.shop,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'sourdough',
              quantity: 1,
              unit: 'loaf',
              confidence: 0.4,
              category: null,
            ),
          ],
          clarifyingQuestions: <String>['Sliced or whole?'],
        ),
      );

      expect(find.text('Sliced or whole?'), findsOneWidget);
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      expect(find.text('CHECK'), findsOneWidget); // low-confidence flag

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final saved = (await tester.runAsync(
        () => shopping.watchAll('test-user').first,
      ))!.single;
      expect(saved.name, 'sourdough');
    });

    testWidgets('returnToShop: confirming a pantry review also resolves the '
        'matching checked shopping rows (AC-SHOP-01)', (
      WidgetTester tester,
    ) async {
      final ingredientId = await shopping.addManualItem(
        userId: 'test-user',
        name: 'milk',
        quantity: 1,
        unit: 'l',
      );
      await shopping.toggleItem(
        id: ingredientId,
        userId: 'test-user',
        checked: true,
      );

      await pumpReview(
        tester,
        const ReviewArgs(
          destination: ReviewDestination.pantry,
          returnToShop: true,
          items: <ReviewItemDraft>[
            ReviewItemDraft(
              reviewId: 'a',
              name: 'milk',
              quantity: 1,
              unit: 'l',
              confidence: 0.9,
              category: 'dairy',
            ),
          ],
        ),
      );

      await tester.tap(find.text('Add 1 item'));
      await tester.pumpAndSettle();

      final shoppingRows = await tester.runAsync(
        () => shopping.watchAll('test-user').first,
      );
      expect(shoppingRows, isEmpty);
    });
  });
}
