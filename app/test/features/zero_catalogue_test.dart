// Pantry, Plan and Shop must be fully usable while no catalogue item has ever synced: a fresh install that is
// offline, or one whose first sync failed.
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/catalogue_sync_lifecycle.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../support/harness.dart';

void main() {
  late AppTestHarness harness;

  setUp(() {
    harness = AppTestHarness(
      httpClient: MockClient(
        (http.Request _) async => throw const SocketException('offline'),
      ),
    );
  });
  tearDown(() => harness.dispose());

  Future<void> failFirstSync(WidgetTester tester) async {
    await tester.runAsync(
      () => harness.container.read(catalogueSyncProvider).sync(),
    );
    final items = await tester.runAsync(
      () => harness.db.select(harness.db.catalogueItems).get(),
    );
    expect(items, isEmpty, reason: 'nothing has synced');
  }

  Future<void> tab(WidgetTester tester, String label) async {
    await tester.tap(
      find.descendant(
        of: find.byType(NavigationBar),
        matching: find.text(label),
      ),
    );
    await tester.pumpAndSettle();
  }

  gleanWidgetTest('with nothing synced, stock, a planned dinner and a manual '
      'shopping item all work across the three tabs', (tester) async {
    await failFirstSync(tester);
    final pantry = harness.container.read(pantryRepositoryProvider);
    await pantry.addItem(
      userId: harness.userId,
      name: 'chicken breast',
      quantity: 500,
      unit: 'g',
      groupId: 'poultry',
    );
    final recipeId = await harness.container
        .read(recipesRepositoryProvider)
        .save(
          userId: harness.userId,
          title: 'Chicken tray bake',
          ingredients: const [
            SaveRecipeIngredient(
              canonicalName: 'chicken breast',
              quantity: 100,
              unit: 'g',
            ),
            SaveRecipeIngredient(
              canonicalName: 'lemon',
              quantity: 1,
              unit: 'units',
            ),
          ],
        );
    final entryId = await harness.container
        .read(planRepositoryProvider)
        .addEntry(
          userId: harness.userId,
          recipeId: recipeId,
          recipeTitle: 'Chicken tray bake',
          servings: 2,
        );
    await harness.container
        .read(shoppingRepositoryProvider)
        .addGapsForRecipe(
          userId: harness.userId,
          recipeId: recipeId,
          servings: 2,
          sourceMealPlanEntryId: entryId,
        );

    await harness.pumpAt(tester, AppRoutes.pantry.path);
    await tester.pumpAndSettle();
    expect(find.textContaining('hicken breast'), findsWidgets);

    await tab(tester, 'Plan');
    expect(find.text('Chicken tray bake'), findsOneWidget);

    await tab(tester, 'Shop');
    expect(find.textContaining('emon'), findsWidgets);
    await tester.enterText(find.byType(TextField), 'Bananas');
    await tester.pump();
    await tester.tap(find.byIcon(Icons.add_rounded));
    await tester.pumpAndSettle();
    expect(find.text('Bananas'), findsOneWidget);
  });
}
