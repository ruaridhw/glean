import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../support/harness.dart';

void main() {
  gleanWidgetTest(
    'a real HTTP auth rejection offers sign-in recovery without hiding local data',
    (tester) async {
      final h = AppTestHarness(
        httpClient: MockClient(
          (_) async => http.Response('{"detail":"expired"}', 403),
        ),
      );
      addTearDown(h.dispose);
      await h.container
          .read(pantryRepositoryProvider)
          .addItem(
            userId: h.userId,
            name: 'chicken breast',
            quantity: 200,
            unit: 'g',
            category: 'poultry',
          );
      await h.pumpAt(tester, AppRoutes.meals.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Search'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'chicken');
      await tester.pump(
        recipeSearchDebounce + const Duration(milliseconds: 50),
      );
      await pumpUntil(
        tester,
        () => find.text('Search failed').evaluate().isNotEmpty,
        description: 'auth rejection UI',
      );
      expect(find.textContaining('Sign in again'), findsOneWidget);
      await tester.tap(
        find.descendant(
          of: find.byType(NavigationBar),
          matching: find.text('Pantry'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('chicken breast'), findsOneWidget);
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        200,
      );
    },
  );
}
