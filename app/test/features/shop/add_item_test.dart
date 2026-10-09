// Widget coverage for the pinned manual-add field: a normal add commits and
// fires the data-commit haptic, and a DB failure surfaces inline while
// leaving the button usable again (AC-SHOP-09 — RN's `setAdding(true)` had
// no `try`/`finally`, so a failure left the button permanently disabled with
// no error shown).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:riverpod/misc.dart';

import '../../data/fixture.dart';
import '../../support/harness.dart';

/// Always fails `addManualItem`, standing in for a DB error the real
/// repository would surface only occasionally (e.g. a disk-full write). This
/// is the "any DB error while adding" half of AC-SHOP-09 — the app-code half
/// (does the screen recover?) is what this test actually exercises.
class _ThrowingShoppingRepository extends ShoppingRepository {
  _ThrowingShoppingRepository(super.db, super.ingredients);

  @override
  Future<int> addManualItem({
    required String userId,
    required String name,
    double? quantity,
    String? unit,
    String? category,
  }) {
    throw Exception('simulated DB failure');
  }
}

void main() {
  group('ShopAddField', () {
    testWidgets('adds an item, fires the commit haptic and clears the field', (
      WidgetTester tester,
    ) async {
      final AppTestHarness harness = AppTestHarness();
      addTearDown(harness.dispose);

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'Bananas');
      await tester.pump();
      await tester.tap(find.byIcon(Icons.add_rounded));
      await tester.pumpAndSettle();

      expect(find.text('Bananas'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        '',
      );
      expect(harness.hapticCalls, contains(HapticWeight.medium));
    });

    testWidgets('a DB error surfaces inline and leaves the add button usable '
        '(AC-SHOP-09)', (WidgetTester tester) async {
      // `_ThrowingShoppingRepository` never touches its db/ingredients
      // (it throws immediately), so this database exists only to satisfy
      // the constructor — it is never the harness's own database.
      final GleanDatabase unusedDb = createTestDatabase();
      addTearDown(unusedDb.close);
      final throwing = _ThrowingShoppingRepository(
        unusedDb,
        IngredientsRepository(unusedDb),
      );

      final AppTestHarness harness = AppTestHarness(
        overrides: <Override>[
          shoppingRepositoryProvider.overrideWithValue(throwing),
        ],
      );
      addTearDown(harness.dispose);

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'Bananas');
      await tester.pump();
      await tester.tap(find.byIcon(Icons.add_rounded));
      await tester.pumpAndSettle();

      expect(find.text('Could not add "Bananas". Try again.'), findsOneWidget);
      // Not stuck spinning, and the button is usable again — RN's bug
      // left this permanently disabled with no explanation.
      expect(find.byType(CircularProgressIndicator), findsNothing);
      final IconButton button = tester.widget<IconButton>(
        find.ancestor(
          of: find.byIcon(Icons.add_rounded),
          matching: find.byType(IconButton),
        ),
      );
      expect(button.onPressed, isNotNull);

      // Retrying is possible — the field still has the text and the
      // button still responds to taps rather than being dead.
      await tester.tap(find.byIcon(Icons.add_rounded));
      await tester.pumpAndSettle();
      expect(find.text('Could not add "Bananas". Try again.'), findsOneWidget);
    });
  });
}
